import json
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

import aiohttp
import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, Security
from fastapi import HTTPException, Query, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer  # 👈 new code
from pydantic import BaseModel

from core import generate_password, _get_user_roles, fetch_role_id
from core.utils import VerifyToken  # 👈 Import the new class

load_dotenv(dotenv_path=".venv/.env")
app = FastAPI()
auth = VerifyToken()

# Define your API keys

token_auth_scheme = HTTPBearer()  # 👈 new code


class ChatRecord(BaseModel):
    sessionid: UUID
    name: str
    emailorphonenumber: str
    datetimeofchat: datetime
    chatduration: int
    chattranscript: str
    chatsummary: str
    category: str
    severity: str
    socialcareeligibility: str
    suggestedcourseofaction: str
    nextsteps: str
    contactrequest: str
    status: str
    rating: str
    feedback: str
    action_taken_notes: Optional[str] = None
    mark_as_complete: Optional[bool] = False


class ManualRecordInput(BaseModel):
    name: str
    email: str
    severity: str
    team: str
    request_details: str
    datetime: datetime


class Comment(BaseModel):
    comment: str


class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


# 👆 We're continuing from the steps above. Append this to your server.py file.


async def get_connection():
    return await asyncpg.connect(
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        database=os.getenv("PGDATABASE"),
        host=os.getenv("PGHOST"),
    )


@app.get("/")
async def health_check():
    return {"message": "FastAPI application is running"}


@app.get("/create_user")
async def create_user(
    sid,
    name: str,
    email: str,
    team: str,
    role: str,
    contact: str,
    auth_result: str = Security(auth.verify),
):
    response, token = await _get_user_roles(sid)
    user_role = json.loads(response)[0]["name"]
    if user_role in [
        "super_admin",
        "front_door_admin",
        "social_care_admin",
        "eip_admin",
    ]:
        async with aiohttp.ClientSession() as session:
            password = await generate_password()
            url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users"
            payload = json.dumps(
                {
                    "email": email,
                    "blocked": False,
                    "email_verified": False,
                    "given_name": name,
                    "family_name": name,
                    "user_metadata": {"team": team, "phone_number": contact},
                    "name": name,
                    "nickname": name,
                    "connection": "Username-Password-Authentication",
                    "password": password,
                    "verify_email": True,
                }
            )
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }
            async with session.post(url, data=payload, headers=headers) as response:
                json_data = await response.json()
                print(json_data)
                json_data["password"] = password
                roles_url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{json_data['user_id']}/roles"
                role_id = await fetch_role_id(role, token)
                payload = json.dumps({"roles": [role_id]})
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                }
                async with session.post(
                    roles_url, data=payload, headers=headers
                ) as role_response:
                    json_data["role_status"] = role_response.status
                    return json_data
    else:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You must be a super admin to perform this action",
        )


@app.get("/delete_user")
async def delete_user(sid, delete_sid, auth_result: str = Security(auth.verify)):
    response, token = await _get_user_roles(sid)
    role = json.loads(response)[0]["name"]
    if (
        role
        in [
            "super_admin",
            "front_door_admin",
            "social_care_admin",
            "eip_admin",
        ]
        and sid != delete_sid
    ):
        async with aiohttp.ClientSession() as session:
            url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{delete_sid}"
            payload = {}
            headers = {"Authorization": f"Bearer {token}"}
            async with session.delete(
                url, data=payload, headers=headers
            ) as role_response:
                if role_response.status == 404:
                    raise HTTPException(status_code=404, detail="User Not Found!")
                else:
                    # status_code = role_response.status
                    response = Response(content="User deleted successfully!")
                    response.status_code = 200
                    return JSONResponse(
                        content={"message": "User deleted successfully!"},
                        status_code=200,
                    )
    else:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You must be a super admin to perform this action",
        )


@app.get("/get_user")
async def get_user(sid, search_sid, auth_result: str = Security(auth.verify)):
    response, token = await _get_user_roles(sid)
    role = json.loads(response)[0]["name"]
    if (
        role in ["super_admin", "front_door_admin", "social_care_admin", "EIP_admin"]
        or sid == search_sid
    ):
        async with aiohttp.ClientSession() as session:
            url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{search_sid}"
            payload = {}
            headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
            async with session.get(url, data=payload, headers=headers) as response:
                if response.status == 404:
                    raise HTTPException(status_code=404, detail="User Not Found!")
                else:
                    return await response.json()
    else:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You must be a super admin to perform this action",
        )


@app.get("/search_users")
async def search_user(
    sid,
    team=None,
    search=None,
    start_date=None,
    end_date=None,
    sort="created_at:-1",
    page=0,
    per_page=10,
    include_totals: bool = True,
    auth_result: str = Security(auth.verify),
):
    response, token = await _get_user_roles(sid)
    role = json.loads(response)[0]["name"]
    if role in ["super_admin", "front_door_admin", "social_care_admin", "eip_admin"]:
        url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users"

        headers = {"Authorization": "Bearer " + token}

        params = {
            "page": page,
            "per_page": per_page,
            "sort": sort,
            "include_totals": str(include_totals).lower(),  # Keep it as boolean
            "search_engine": "v3",
        }

        # Add filters if provided
        query = []
        if team:
            query.append(f"user_metadata.team:{team}")
        if search:
            query.append(f"(name:*{search}* OR email:*{search}*)")
        if start_date and end_date:
            query.append(f"created_at:[{start_date} TO {end_date}]")
        elif start_date:
            query.append(f"created_at:[{start_date} TO *]")
        elif end_date:
            query.append(f"created_at:[* TO {end_date}]")

        params["q"] = " AND ".join(query)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise HTTPException(
                        status_code=response.status, detail=await response.json()
                    )


@app.get("/get_roles")
async def get_user_roles(sid, auth_result: str = Security(auth.verify)):
    async with aiohttp.ClientSession() as session:
        payload = json.dumps(
            {
                "client_id": os.getenv("AUTH0_CLIENT_ID"),
                "client_secret": os.getenv("AUTH0_CLIENT_SECRET"),
                "audience": f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/",
                "grant_type": "client_credentials",
            }
        )
        headers = {"content-type": "application/json"}

        async with session.post(
            f"https://{os.getenv('AUTH0_DOMAIN')}/oauth/token",
            data=payload,
            headers=headers,
        ) as response:
            json_data = await response.json()

        url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{sid}/roles"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {json_data.get('access_token')}",
        }

        async with session.get(url, headers=headers) as response:
            return await response.text()


@app.get("/session-data")
async def get_session_data(
    team: Optional[str] = None,
    search: Optional[str] = None,
    page: Optional[int] = Query(1, ge=1),
    limit: Optional[int] = Query(10, le=100),
    triaging_confirmed: Optional[str] = None,
    history: Optional[bool] = None,
    auth_result: str = Security(auth.verify),
):
    count_query = """ 
    SELECT COUNT(*) FROM (
        SELECT sessionid, category, triaging_confirmed, name, mark_as_complete FROM chatrecords
        UNION
        SELECT sessionid, category, triaging_confirmed, name, mark_as_complete FROM manualrecords
    ) AS combined
    """
    select_query = """
    SELECT sessionid, name, emailorphonenumber, datetimeofchat, severity, socialcareeligibility, triaging_confirmed, mark_as_complete, category, flag
    FROM (
        SELECT sessionid, name, emailorphonenumber, datetimeofchat, severity, socialcareeligibility, triaging_confirmed, mark_as_complete, category, flag
        FROM chatrecords
        UNION ALL
        SELECT sessionid, name, emailorphonenumber, datetime, severity, socialcareeligibility, triaging_confirmed, mark_as_complete, category, flag
        FROM manualrecords
    ) AS combined
    """
    conditions = []
    if team:
        conditions.append(f"category = '{team}'")
    else:
        conditions.append(
            "category IN ('Social Care', 'EIP', 'CAFD', 'Not enough Information')"
        )
    if search:
        conditions.append(f"name ILIKE '%{search}%'")
    if triaging_confirmed:
        conditions.append(f"triaging_confirmed = '{triaging_confirmed}'")
    if history:
        conditions.append(f"mark_as_complete = '{history}'")
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        select_query += where_clause
        count_query += where_clause
    try:
        conn = await get_connection()
        total_count = await conn.fetchval(count_query)
        select_query += (
            f" ORDER BY datetimeofchat DESC LIMIT {limit} OFFSET {(page - 1) * limit}"
        )
        records = await conn.fetch(select_query)
        await conn.close()
        return {"total_count": total_count, "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session")
async def get_session_by_id(
    sid: UUID, flag: str, auth_result: str = Security(auth.verify)
):
    if flag == "manual":
        select_query = """
           SELECT m.sessionid, m.severity, m.category, m.mark_as_complete, m.request_details,
                  c.comment_id, c.comment, c.email
           FROM manualrecords m
           LEFT JOIN comments c ON m.sessionid = c.sessionid
           WHERE m.sessionid = $1
           """
    elif flag == "chat":
        select_query = """
           SELECT r.sessionid, r.severity, r.category, r.mark_as_complete, r.chatsummary, r.chattranscript,
                  c.comment_id, c.comment, c.email
           FROM chatrecords r
           LEFT JOIN comments c ON r.sessionid = c.sessionid
           WHERE r.sessionid = $1
           """
    else:
        raise HTTPException(status_code=400, detail="Invalid flag value")

    try:
        conn = await get_connection()
        records = await conn.fetch(select_query, sid)
        await conn.close()

        if not records:
            raise HTTPException(status_code=404, detail="Session ID not found")

        if flag == "manual":
            record = records[0]
            return {
                "sessionid": record["sessionid"],
                "severity": record["severity"],
                "category": record["category"],
                "mark_as_complete": record["mark_as_complete"],
                "request_details": record["request_details"],
                "comments": [
                    {
                        "comment_id": record["comment_id"],
                        "comment": record["comment"],
                        "email": record["email"],
                    }
                    for record in records
                    if record["comment_id"] is not None
                ],
            }
        else:
            record = records[0]
            comments = [
                {
                    "comment_id": record["comment_id"],
                    "comment": record["comment"],
                    "email": record["email"],
                }
                for record in records
                if record["comment_id"] is not None
            ]
            return {
                "sessionid": record["sessionid"],
                "severity": record["severity"],
                "category": record["category"],
                "mark_as_complete": record["mark_as_complete"],
                "chatsummary": record["chatsummary"],
                "chattranscript": record["chattranscript"],
                "comments": comments,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{sid}/comments")
async def add_comment_to_session(
    sid: UUID,
    comment: Comment,
    email: str,
    flag: str,
    auth_result: str = Security(auth.verify),
):
    if flag == "manual":
        insert_query = """
        INSERT INTO comments (sessionid, comment, email)
        VALUES ((SELECT sessionid FROM manualrecords WHERE sessionid = $1), $2, $3)
        RETURNING comment_id
        """
    elif flag == "chat":
        insert_query = """
        INSERT INTO comments (sessionid, comment, email)
        VALUES ((SELECT sessionid FROM chatrecords WHERE sessionid = $1), $2, $3)
        RETURNING comment_id
        """
    else:
        raise HTTPException(status_code=400, detail="Invalid flag value")

    try:
        conn = await get_connection()
        record_id = await conn.fetchval(insert_query, sid, comment.comment, email)
        await conn.close()
        if record_id:
            return {"comment_id": record_id, "comment": comment.comment}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update-chat-urgency")
async def update_chat_urgency(
    sid: UUID, urgency: str, flag: str, auth_result: str = Security(auth.verify)
):
    if flag == "manual":
        update_query = """
        UPDATE manualrecords
        SET severity = $1
        WHERE sessionid = $2
        """
    elif flag == "chat":
        update_query = """
        UPDATE chatrecords
        SET severity = $1
        WHERE sessionid = $2
        """
    else:
        raise HTTPException(status_code=400, detail="Invalid flag value")

    try:
        conn = await get_connection()
        result = await conn.execute(update_query, urgency, sid)
        await conn.close()
        if result == "UPDATE 1":
            return {"message": "Chat urgency updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update-chat-team")
async def update_chat_team(
    sid: UUID, team: str, flag: str, auth_result: str = Security(auth.verify)
):
    if flag == "manual":
        update_query = """
        UPDATE manualrecords
        SET category = $1, triaging_confirmed = True
        WHERE sessionid = $2
        """
    elif flag == "chat":
        update_query = """
        UPDATE chatrecords
        SET category = $1, triaging_confirmed = True
        WHERE sessionid = $2
        """
    else:
        raise HTTPException(status_code=400, detail="Invalid flag value")

    try:
        conn = await get_connection()
        result = await conn.execute(update_query, team, sid)
        await conn.close()
        if result == "UPDATE 1":
            return {"message": "Chat team updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/take-action")
async def take_action(
    sid: UUID,
    action_taken_notes: str,
    mark_as_complete: bool,
    flag: str,
    auth_result: str = Security(auth.verify),
):
    if flag == "manual":
        update_query = """
        UPDATE manualrecords
        SET action_taken_notes = $1, mark_as_complete = $2
        WHERE sessionid = $3
        """
    elif flag == "chat":
        update_query = """
        UPDATE chatrecords
        SET action_taken_notes = $1, mark_as_complete = $2
        WHERE sessionid = $3
        """
    else:
        raise HTTPException(status_code=400, detail="Invalid flag value")

    try:
        conn = await get_connection()
        result = await conn.execute(
            update_query, action_taken_notes, mark_as_complete, sid
        )
        await conn.close()
        if result == "UPDATE 1":
            return {"message": "Action taken successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add-manual-record")
async def add_manual_record(
    record: ManualRecordInput, auth_result: str = Security(auth.verify)
):
    insert_query = """
    INSERT INTO manualrecords (name, emailorphonenumber, severity, category, request_details, datetime)
    VALUES ($1, $2, $3, $4, $5, $6)
    """
    try:
        conn = await get_connection()
        await conn.execute(
            insert_query,
            record.name,
            record.email,
            record.severity,
            record.team,
            record.request_details,
            record.datetime,
        )
        await conn.close()
        return {"message": "Manual record added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
