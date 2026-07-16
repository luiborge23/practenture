#!/usr/bin/env python3
"""Destructive-safe live HTTP QA: unique 20-team, 8-round session, then cleanup."""
import json, os, sys, time, urllib.error, urllib.request
BASE=os.environ.get("BIZSIMAI_E2E_BASE_URL","http://127.0.0.1") .rstrip("/")

def request(method,path,payload=None,token=None,expected=(200,)):
    data=None if payload is None else json.dumps(payload).encode()
    headers={"Accept":"application/json"}
    if data is not None: headers["Content-Type"]="application/json"
    if token: headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read(); status=r.status
    except urllib.error.HTTPError as e:
        raw=e.read(); status=e.code
    if status not in expected:
        raise AssertionError(f"{method} {path}: HTTP {status}: {raw[:500]!r}")
    return json.loads(raw) if raw else None

def decision(i,r):
    s=i%5
    return {
      "wholesalePrice":42.0+s*3+r*.15,"internetPrice":48.0+s*3+r*.15,
      "amazonPrice":46.0+s*3+r*.15,"privateLabelBidPrice":34.0+s,
      "privateLabelMaxUnits":800+s*50,"amazonAdBudget":1000.0+s*250,
      "materialsQuality":"superior" if s>=3 else "standard",
      "stylingBudget":3000.0+s*600,"modelsOffered":3+s,
      "tqmInvestment":2000.0+s*500,"advertisingBudget":8000.0+s*1200,
      "celebrityEndorsement":["none","local","local","national","national"][s],
      "retailOutlets":10+s*2,"mailInRebate":float(s),
      "deliveryTime":"rush" if s>=3 else "standard",
      "freeShippingThreshold":100.0-s*5,"tiktokBudget":1000.0+s*300,
      "instagramBudget":1200.0+s*350,"youtubeBudget":900.0+s*250,
      "influencerTier":"micro" if s>=2 else "nano",
      "baseWage":25000.0+s*750,"incentivePay":0.5+s*.1,
      "trainingHours":20.0+s*4,"bestPracticesInvestment":1000.0+s*300,
      "productionQuantity":6500+s*500,"overtimePercent":float(s*3),
      "csrInvestment":1000.0+s*500,"dividendsPerShare":s*.1,
      "newLoanAmount":0.0,"sharesBuyback":0,"sharesIssued":0,
      "fulfillmentMethod":"fba" if s>=2 else "fbm"
    }

def main():
    user=os.environ.get("BIZSIMAI_PROFESSOR_USERNAME","professor")
    password=os.environ["BIZSIMAI_PROFESSOR_PASSWORD"]
    login=request("POST","/api/auth/login",{"username":user,"password":password,"provider":"password"})
    token=login.get("accessToken") or login.get("access_token")
    assert token, "login response missing token"
    stamp=str(int(time.time()))
    created=request("POST","/api/sessions",{
      "config":{"totalRounds":8,"numberOfAICompetitors":3,"randomSeed":20260716,
                "startingCash":500000.0,"initialEquity":300000.0,
                "plantCapacity":12000,"baseMarketDemand":50000},
      "teams":[],"created_by":"live-qa-"+stamp,"maxHumanTeams":30
    },token=token,expected=(200,201))
    code=created["code"]
    teams=[]; submissions=0; process_calls=0; counts=[]
    try:
      for i in range(1,21):
        name=f"LIVEQA-{stamp}-{i:02d}"
        joined=request("PUT",f"/api/sessions/{code}/join",{"teamName":name,"studentId":f"QA{stamp}{i:02d}"},expected=(200,))
        assert joined["teamId"]==name, joined
        teams.append(name)
      assert len(set(teams))==20
      for rnd in range(1,9):
        for i,name in enumerate(teams,1):
          response=request("POST",f"/api/sessions/{code}/submit_decision",
            {"round":rnd,"teamId":name,"decision":decision(i,rnd)},expected=(200,204))
          if response is not None: assert response.get("teamId",name)==name
          submissions+=1
        before=request("GET",f"/api/sessions/{code}/status",token=token)
        assert before["currentRound"]==rnd and before["teamsSubmitted"]==20, before
        processed=request("POST",f"/api/sessions/{code}/process_round",token=token)
        process_calls+=1
        assert processed["round"]==rnd, processed
        rows=processed["results"]
        assert len(rows)==23 and len({x["teamId"] for x in rows})==23
        counts.append(len(rows))
        after=request("GET",f"/api/sessions/{code}/status",token=token)
        assert after["currentRound"]==(rnd+1 if rnd<8 else 8), after
        assert after["state"]==("active" if rnd<8 else "finished"), after
      stored=request("GET",f"/api/sessions/{code}/results",token=token)
      assert set(stored["results"])=={str(x) for x in range(1,9)}
      assert all(len(x)==23 for x in stored["results"].values())
      board=request("GET",f"/api/sessions/{code}/leaderboard",token=token)["leaderboard"]
      assert len(board)==23
      assert [x["rank"] for x in board]==list(range(1,24))
      scores=[x["totalScore"] for x in board]
      assert scores==sorted(scores,reverse=True)
      print(json.dumps({"status":"PASS","session":code,"humanTeams":20,"aiTeams":3,
        "submissions":submissions,"processRoundCalls":process_calls,"resultsPerRound":counts,
        "storedRounds":len(stored["results"]),"leaderboardEntries":len(board),
        "finalState":"finished"},sort_keys=True))
    finally:
      try:
        response=request("DELETE",f"/api/sessions/{code}",token=token,expected=(200,204,404,405))
        print(json.dumps({"cleanupSession":code,"cleanup":"attempted"}))
      except Exception as exc:
        print(json.dumps({"cleanupSession":code,"cleanupError":str(exc)}),file=sys.stderr)

if __name__=="__main__": main()
