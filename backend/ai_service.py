"""Practenture AI Service — Amazon Bedrock integration via boto3.

Provides Claude Sonnet 4 inference for:
- AI-generated business scenarios (professor-facing)
- Automated feedback on student decisions
- Smart hints/recommendations during simulation
- Professor dashboard AI insights

Requires EC2 IAM role with bedrock:InvokeModel permission.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

BEDROCK_REGION = os.environ.get("PRACTENTURE_BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL = os.environ.get(
    "PRACTENTURE_BEDROCK_MODEL", "anthropic.claude-sonnet-4-6"
)
BEDROCK_MAX_TOKENS = int(os.environ.get("PRACTENTURE_BEDROCK_MAX_TOKENS", "2048"))
BEDROCK_TEMPERATURE = float(os.environ.get("PRACTENTURE_BEDROCK_TEMPERATURE", "0.7"))
BEDROCK_ENABLED = os.environ.get("PRACTENTURE_BEDROCK_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)

# Verify boto3 is available; if not, disable Bedrock automatically
try:
    import boto3  # noqa: F401
except ImportError:
    BEDROCK_ENABLED = False

# Retry settings
BEDROCK_MAX_RETRIES = int(os.environ.get("PRACTENTURE_BEDROCK_MAX_RETRIES", "3"))
BEDROCK_RETRY_BASE_DELAY = float(os.environ.get("PRACTENTURE_BEDROCK_RETRY_BASE_DELAY", "1.0"))


def _get_bedrock_client():
    """Create or return a cached Bedrock runtime client."""
    import boto3

    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def _build_system_prompt(context: str = "") -> str:
    """Build the system prompt for Claude in Practenture context."""
    base = (
        "You are an expert business simulation advisor for Practenture, a classroom business simulation platform. "
        "Students make decisions about pricing, marketing, production, HR, and strategy for a simulated company. "
        "You provide clear, educational feedback that helps students learn business concepts.\n\n"
    )
    if context:
        base += f"Context:\n{context}\n\n"
    return base


def _build_user_prompt(prompt: str) -> List[Dict[str, Any]]:
    """Build the messages array for Claude API."""
    return [{"role": "user", "content": prompt}]


def _invoke_bedrock(system_prompt: str, user_messages: List[Dict[str, Any]]) -> Optional[str]:
    """Call Bedrock with retry logic. Returns the assistant's text response or None on failure."""
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError

    client = _get_bedrock_client()

    body = {
        "system": system_prompt,
        "messages": user_messages,
        "max_tokens": BEDROCK_MAX_TOKENS,
        "temperature": BEDROCK_TEMPERATURE,
    }

    last_error = None
    for attempt in range(1, BEDROCK_MAX_RETRIES + 1):
        try:
            response = client.invoke_model(
                modelId=BEDROCK_MODEL,
                body=json.dumps(body),
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"]

        except (ClientError, EndpointConnectionError) as e:
            last_error = e
            logger.warning(
                "Bedrock invoke attempt %d/%d failed: %s",
                attempt, BEDROCK_MAX_RETRIES, e,
            )
            if attempt < BEDROCK_MAX_RETRIES:
                delay = BEDROCK_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                time.sleep(delay)

        except Exception as e:
            logger.error("Unexpected Bedrock error: %s", e)
            return None

    logger.error(
        "Bedrock invoke failed after %d attempts: %s",
        BEDROCK_MAX_RETRIES, last_error,
    )
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def generate_scenario(
    industry: str = "consumer_electronics",
    difficulty: str = "medium",
    round_num: int = 1,
    total_rounds: int = 20,
) -> str:
    """Generate an AI business scenario for students.

    Args:
        industry: Business sector (e.g., consumer_electronics, retail, food_beverage)
        difficulty: easy, medium, hard
        round_num: Current round number
        total_rounds: Total rounds in session

    Returns:
        Generated scenario text, or fallback message if Bedrock unavailable.
    """
    if not BEDROCK_ENABLED:
        return _fallback_scenario(industry, difficulty, round_num)

    system = _build_system_prompt(
        f"You are generating business scenarios for a classroom simulation. "
        f"Scenarios should be realistic, educational, and include market conditions, "
        f"competitor actions, and unexpected events that affect business decisions."
    )

    prompt = (
        f"Generate a realistic business scenario for round {round_num} of {total_rounds} "
        f"in the {industry} industry at {difficulty} difficulty.\n\n"
        f"The scenario should include:\n"
        f"1. Market conditions (demand trends, competitor moves)\n"
        f"2. An unexpected event or challenge\n"
        f"3. Specific numbers and data students can use in their decisions\n"
        f"4. A brief 'What happened this round?' summary\n\n"
        f"Keep it under 300 words. Format with clear headings."
    )

    result = _invoke_bedrock(system, _build_user_prompt(prompt))
    return result or _fallback_scenario(industry, difficulty, round_num)


def provide_feedback(
    student_decision: Dict[str, Any],
    round_result: Dict[str, Any],
    context: str = "",
) -> str:
    """Provide educational feedback on student decisions.

    Args:
        student_decision: The PlayerDecision dict submitted by the student
        round_result: The RoundResult dict with outcomes
        context: Additional context (e.g., competitor actions, market conditions)

    Returns:
        Feedback text, or fallback if Bedrock unavailable.
    """
    if not BEDROCK_ENABLED:
        return _fallback_feedback(student_decision, round_result)

    system = _build_system_prompt(
        "You are a business professor providing constructive, educational feedback. "
        "Be specific about what the student did well and where they could improve. "
        "Connect their decisions to business concepts (pricing strategy, cost management, etc.)."
    )

    decision_summary = (
        f"Wholesale: ${student_decision.get('wholesalePrice', 0):.2f}, "
        f"Internet: ${student_decision.get('internetPrice', 0):.2f}, "
        f"Amazon: ${student_decision.get('amazonPrice', 0):.2f}\n"
        f"Materials Quality: {student_decision.get('materialsQuality', 0):.2f}\n"
        f"Marketing: ${student_decision.get('marketingInvestment', 0):,.0f}\n"
        f"Advertising: ${student_decision.get('advertisingBudget', 0):,.0f}\n"
        f"TQM: ${student_decision.get('tqmInvestment', 0):,.0f}\n"
        f"R&D: ${student_decision.get('rdInvestment', 0):,.0f}\n"
        f"Production: {student_decision.get('productionQuantity', 0)} units\n"
        f"Base Wage: ${student_decision.get('baseWage', 0):,.0f}\n"
        f"CSR: ${student_decision.get('csrInvestment', 0):,.0f}"
    )

    result_summary = (
        f"Revenue: ${round_result.get('revenue', 0):,.2f}\n"
        f"Profit: ${round_result.get('profit', 0):,.2f}\n"
        f"Market Share: {round_result.get('marketShare', 0):.1f}%\n"
        f"S/Q Rating: {round_result.get('sqRating', 0):.1f}\n"
        f"Reputation: {round_result.get('reputation', 0):.1f}\n"
        f"Cash: ${round_result.get('cash', 0):,.2f}\n"
        f"Stock Price: ${round_result.get('stockPrice', 0):.2f}\n"
        f"Total Score: {round_result.get('totalScore', 0):.1f}"
    )

    prompt = (
        f"Provide educational feedback on this student's business simulation decisions.\n\n"
        f"DECISIONS:\n{decision_summary}\n\n"
        f"RESULTS:\n{result_summary}\n"
    )
    if context:
        prompt += f"\nCONTEXT:\n{context}\n"

    prompt += (
        "\n\nGive 2-3 specific strengths, 2-3 areas for improvement, "
        "and one actionable recommendation. Keep it under 250 words."
    )

    result = _invoke_bedrock(system, _build_user_prompt(prompt))
    return result or _fallback_feedback(student_decision, round_result)


def generate_hint(
    current_state: Dict[str, Any],
    problem: str = "",
) -> str:
    """Generate a smart hint/recommendation for students.

    Args:
        current_state: Current team state (cash, stock price, market share, etc.)
        problem: Specific problem the student is facing (e.g., "low market share")

    Returns:
        Hint text, or fallback if Bedrock unavailable.
    """
    if not BEDROCK_ENABLED:
        return _fallback_hint(current_state, problem)

    system = _build_system_prompt(
        "You are a business simulation advisor giving concise, actionable hints. "
        "Be encouraging but direct. Focus on the most impactful single recommendation."
    )

    state_summary = (
        f"Cash: ${current_state.get('cash', 0):,.2f}\n"
        f"Stock Price: ${current_state.get('stockPrice', 0):.2f}\n"
        f"Market Share: {current_state.get('marketShare', 0):.1f}%\n"
        f"Reputation: {current_state.get('reputation', 0):.1f}\n"
        f"S/Q Rating: {current_state.get('sqRating', 0):.1f}\n"
        f"Cumulative Profit: ${current_state.get('cumulativeProfit', 0):,.2f}\n"
        f"Credit Score: {current_state.get('creditScore', 0):.1f}"
    )

    prompt = f"Based on the current state:\n{state_summary}\n\n"
    if problem:
        prompt += f"The student is struggling with: {problem}\n\n"
    prompt += "Give one specific, actionable hint (max 2 sentences) that could help improve their performance."

    result = _invoke_bedrock(system, _build_user_prompt(prompt))
    return result or _fallback_hint(current_state, problem)


def generate_insights(
    session_results: List[Dict[str, Any]],
    team_count: int = 1,
) -> str:
    """Generate professor-facing AI insights about the simulation.

    Args:
        session_results: List of all round results across teams
        team_count: Number of teams in the simulation

    Returns:
        Insights text, or fallback if Bedrock unavailable.
    """
    if not BEDROCK_ENABLED:
        return _fallback_insights(session_results, team_count)

    system = _build_system_prompt(
        "You are analyzing business simulation data for a professor. "
        "Provide actionable insights about class performance, common mistakes, "
        "and teaching opportunities. Be data-driven and specific."
    )

    # Summarize results for the prompt
    summary_lines = []
    for result in session_results[:20]:  # Limit to avoid token overflow
        summary_lines.append(
            f"Round {result.get('round', '?')}: "
            f"Avg Revenue: ${result.get('avg_revenue', 0):,.0f}, "
            f"Avg Profit: ${result.get('avg_profit', 0):,.0f}, "
            f"Avg Market Share: {result.get('avg_market_share', 0):.1f}%"
        )

    prompt = (
        f"Analyze the following business simulation data for {team_count} teams.\n\n"
        f"ROUND SUMMARY:\n" + "\n".join(summary_lines) + "\n\n"
        f"Provide:\n"
        f"1. Top 3 class-wide trends\n"
        f"2. Common student mistakes observed\n"
        f"3. Teaching points to highlight in debrief\n"
        f"4. One recommendation for the professor\n\n"
        f"Keep it under 300 words."
    )

    result = _invoke_bedrock(system, _build_user_prompt(prompt))
    return result or _fallback_insights(session_results, team_count)


# ── Fallbacks (when Bedrock is disabled or unavailable) ─────────────────────

def _fallback_scenario(industry: str, difficulty: str, round_num: int) -> str:
    """Fallback scenario when Bedrock is unavailable."""
    return (
        f"Round {round_num} Scenario ({industry}, {difficulty}):\n\n"
        f"Market conditions are stable. Competitors are maintaining current pricing. "
        f"Consumer demand is at expected levels for this industry.\n\n"
        f"Focus on optimizing your pricing strategy and managing production costs. "
        f"Consider whether investing in quality improvement or marketing would give you a competitive edge."
    )


def _fallback_feedback(decision: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Fallback feedback when Bedrock is unavailable."""
    profit = result.get("profit", 0)
    if profit > 0:
        return (
            f"Your decisions resulted in a profit of ${profit:,.2f}. "
            f"Review your pricing vs. production costs to identify optimization opportunities."
        )
    return (
        f"Your decisions resulted in a loss of ${abs(profit):,.2f}. "
        f"Consider reducing production costs, adjusting prices upward, or cutting unnecessary marketing spend."
    )


def _fallback_hint(state: Dict[str, Any], problem: str) -> str:
    """Fallback hint when Bedrock is unavailable."""
    if problem:
        return f"Consider reviewing your strategy for '{problem}'. Check your pricing, production levels, and marketing spend."
    cash = state.get("cash", 0)
    if cash < 50000:
        return "Your cash reserves are low. Consider reducing production or taking out a loan to maintain operations."
    return "Your simulation is running smoothly. Look for opportunities to increase market share through quality improvements or marketing."


def _fallback_insights(results: List[Dict[str, Any]], team_count: int) -> str:
    """Fallback insights when Bedrock is unavailable."""
    return (
        f"Simulation Summary ({team_count} teams):\n\n"
        f"Review the round results to identify trends. "
        f"Look for patterns in pricing strategies, quality investments, and their impact on market share and profitability."
    )
