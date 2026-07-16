"""Class management endpoints — professor creates classes, students join by code."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, verify_professor, verify_student_or_professor
from database import db
from models import (
    CreateClassRequest,
    ClassResponse,
    JoinClassRequest,
    EnrollStudentResponse,
    ClassListResponse,
    StudentClassListResponse,
    ClassStudentsResponse,
)

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.post("", response_model=ClassResponse, status_code=201)
async def create_class(req: CreateClassRequest, user=Depends(verify_professor)):
    """Professor creates a new class. Returns class with join_code for students."""
    from audit import log_event

    result = db.create_class(
        professor_user_id=user["sub"],
        name=req.name,
        description=req.description,
    )
    log_event(actor=user["sub"], action="class_created", details={"class_id": result["id"], "name": req.name})
    return ClassResponse(**result)


@router.get("", response_model=ClassListResponse)
async def list_classes(user=Depends(verify_professor)):
    """Professor lists all their classes."""
    classes = db.list_classes_by_professor(user["sub"])
    return ClassListResponse(classes=[ClassResponse(**c) for c in classes])


@router.get("/my/classes", response_model=StudentClassListResponse)
async def my_classes(user=Depends(verify_student_or_professor)):
    """Student lists all classes they're enrolled in."""
    classes = db.get_student_classes(user["sub"])
    return StudentClassListResponse(classes=[ClassResponse(**c) for c in classes])


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(class_id: str, user=Depends(verify_professor)):
    """Get details of a specific class."""
    cls = db.get_class(class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    if cls["professor_user_id"] != user["sub"] and user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Not your class")
    return ClassResponse(**cls)


@router.post("/join", response_model=EnrollStudentResponse)
async def join_class(req: JoinClassRequest, user=Depends(verify_student_or_professor)):
    """Student joins a class using the class join code."""
    cls = db.get_class_by_join_code(req.join_code)
    if not cls:
        raise HTTPException(status_code=404, detail="Invalid or inactive class code")

    # Check if professor still exists
    prof = db.get_user(cls["professor_user_id"])
    if not prof:
        raise HTTPException(status_code=410, detail="This class is no longer available — the professor account has been removed")

    # Check if student already enrolled
    existing = db.get_student_classes(user["sub"])
    for enrolled_cls in existing:
        if enrolled_cls["id"] == cls["id"]:
            return EnrollStudentResponse(
                class_id=cls["id"],
                class_name=cls["name"],
                message="Already enrolled in this class",
            )

    success = db.enroll_student(cls["id"], user["sub"])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to enroll in class. Please try again.")

    return EnrollStudentResponse(
        class_id=cls["id"],
        class_name=cls["name"],
    )


@router.get("/{class_id}/students", response_model=ClassStudentsResponse)
async def get_class_students(class_id: str, user=Depends(verify_professor)):
    """Professor lists all students enrolled in a class."""
    cls = db.get_class(class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    if cls["professor_user_id"] != user["sub"] and user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Not your class")

    students = db.get_class_students(class_id)
    return ClassStudentsResponse(students=students)
