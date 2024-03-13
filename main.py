import json
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

import aiohttp
import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, Security
from fastapi import HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer  # 👈 new code
from pydantic import BaseModel

from core import generate_password, _get_user_roles, fetch_role_id
from core.utils import VerifyToken  # 👈 Import the new class

load_dotenv(dotenv_path='.venv/.env')
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


class Comment(BaseModel):
    comment: str


class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


# 👆 We're continuing from the steps above. Append this to your server.py file.


async def get_connection():
    return await asyncpg.connect(user=os.getenv('PGUSER'), password=os.getenv('PGPASSWORD'),
                                 database=os.getenv('PGDATABASE'), host=os.getenv('PGHOST'))


@app.get("/")
async def health_check():
    return {"message": "FastAPI application is running"}


@app.get("/create_user")
async def create_user(sid, name: str, email: str, team: str, role: str, contact: str, auth_result: str = Security(auth.verify)):
    response, token = await _get_user_roles(sid)
    user_role = json.loads(response)[0]['name']
    if user_role in ['super_admin', 'front_door_admin', 'social_care_admin', 'EIP_admin']:
        async with aiohttp.ClientSession() as session:
            password = await generate_password()
            url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users"
            payload = json.dumps({
                "email": email,
                "blocked": False,
                "email_verified": False,
                "phone_number": contact,
                "phone_verified": True,
                "given_name": name,
                "family_name": name,
                "app_metadata": {'team': team},
                "name": name,
                "nickname": name,
                "connection": "Username-Password-Authentication",
                "password": password,
                "verify_email": True,
            })
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            async with session.post(url, data=payload,
                                    headers=headers) as response:
                json_data = await response.json()
                json_data['password'] = password
                roles_url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{json_data['user_id']}/roles"
                role_id = await fetch_role_id(role, token)
                payload = json.dumps({

                    "roles": [
                        role_id
                    ]
                })
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {token}'
                }
                async with session.post(roles_url, data=payload,
                                        headers=headers) as role_response:
                    json_data['role_status'] = role_response.status
                    return json_data
    else:
        raise HTTPException(status_code=403, detail="Forbidden: You must be a super admin to perform this action")


@app.get("/delete_user")
async def delete_user(sid, delete_sid, auth_result: str = Security(auth.verify)):
    response, token = await _get_user_roles(sid)
    role = json.loads(response)[0]['name']
    if role in ['super_admin', 'front_door_admin', 'social_care_admin', 'EIP_admin'] and sid != delete_sid:
        async with aiohttp.ClientSession() as session:
            url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{delete_sid}"
            payload = {}
            headers = {
                'Authorization': f'Bearer {token}'
            }
            async with session.delete(url, data=payload,
                                      headers=headers) as role_response:
                if role_response.status == 404:
                    raise HTTPException(status_code=404, detail="User Not Found!")
                else:
                    return JSONResponse(content='User deleted successfully!', status_code=role_response.status)
    else:
        raise HTTPException(status_code=403, detail="Forbidden: You must be a super admin to perform this action")


@app.get("/get_user")
async def search_user(sid, search_sid, auth_result: str = Security(auth.verify)):
    response, token = await _get_user_roles(sid)
    role = json.loads(response)[0]['name']
    if role in ['super_admin', 'front_door_admin', 'social_care_admin', 'EIP_admin'] or sid == search_sid:
        async with aiohttp.ClientSession() as session:
            url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{search_sid}"
            payload = {}
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            async with session.get(url, data=payload,
                                   headers=headers) as response:
                if response.status == 404:
                    raise HTTPException(status_code=404, detail="User Not Found!")
                else:
                    return await response.json()
    else:
        raise HTTPException(status_code=403, detail="Forbidden: You must be a super admin to perform this action")


@app.get("/search_users")
async def search_user(sid, team=None, search=None, start_date=None, end_date=None, sort="created_at:-1", page=0,
                      per_page=10, include_totals: bool = True, auth_result: str = Security(auth.verify)):
    response, token = await _get_user_roles(sid)
    role = json.loads(response)[0]['name']
    if role in ['super_admin', 'front_door_admin', 'social_care_admin', 'EIP_admin']:
        url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users"

        headers = {
            "Authorization": "Bearer " + token
        }

        params = {
            "page": page,
            "per_page": per_page,
            "sort": sort,
            'include_totals': str(include_totals).lower()  # Keep it as boolean
        }

        # Add filters if provided
        if team:
            params["q"] = f"app_metadata.team:{team}"
        if search:
            params["q"] = search
        if start_date:
            params["q"] = f"{params.get('q', '')} AND created_at:[{start_date} TO *]"
        if end_date:
            params["q"] = f"{params.get('q', '')} AND created_at:[* TO {end_date}]"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise HTTPException(status_code=response.status, detail=await response.json())


@app.get("/get_roles")
async def get_user_roles(sid, auth_result: str = Security(auth.verify)):
    async with aiohttp.ClientSession() as session:
        payload = json.dumps({
            "client_id": os.getenv('AUTH0_CLIENT_ID'),
            "client_secret": os.getenv('AUTH0_CLIENT_SECRET'),
            "audience": f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/",
            "grant_type": "client_credentials"
        })
        headers = {'content-type': "application/json"}

        async with session.post(f"https://{os.getenv('AUTH0_DOMAIN')}/oauth/token", data=payload,
                                headers=headers) as response:
            json_data = await response.json()

        url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/users/{sid}/roles"
        headers = {
            'Accept': 'application/json',
            'Authorization': f"Bearer {json_data.get('access_token')}"
        }

        async with session.get(url, headers=headers) as response:
            return await response.text()


@app.get("/session-data")
async def get_session_data(team: Optional[str] = None, search: Optional[str] = None,
                           page: Optional[int] = Query(1, ge=1),
                           limit: Optional[int] = Query(10, le=100), triaging_confirmed: Optional[str] = None,
                           auth_result: str = Security(auth.verify)):
    count_query = """ 
    SELECT COUNT(*) FROM chatrecords
    """
    select_query = """
    SELECT sessionid, name, emailorphonenumber, datetimeofchat, severity, socialcareeligibility, triaging_confirmed, mark_as_complete, category
    FROM chatrecords
    """
    conditions = []
    if team:
        conditions.append(f"category = '{team}'")
    else:
        conditions.append("category IN ('Social Care', 'EIP', 'Not enough Information')")
    if search:
        conditions.append(f"name ILIKE '%{search}%'")
    if triaging_confirmed:
        conditions.append(f"triaging_confirmed = '{triaging_confirmed}'")
    if conditions:
        select_query += " WHERE " + " AND ".join(conditions)
        count_query += " WHERE " + " AND ".join(conditions)
    # print(select_query)
    try:
        conn = await get_connection()
        total_count = await conn.fetchval(count_query)
        select_query += f" ORDER BY datetimeofchat DESC LIMIT {limit} OFFSET {(page - 1) * limit}"
        records = await conn.fetch(select_query)
        await conn.close()
        return {"total_count": total_count, "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session")
async def get_session_by_id(sid: UUID, auth_result: str = Security(auth.verify)):
    select_query = """
    SELECT c.comment_id, c.comment, c.email, r.sessionid, r.severity, r.category, r.mark_as_complete, r.chatsummary, r.chattranscript
    FROM chatrecords r
    LEFT JOIN comments c ON r.sessionid = c.sessionid
    WHERE r.sessionid = $1
    """
    try:
        conn = await get_connection()
        records = await conn.fetch(select_query, sid)
        await conn.close()
        if records:
            return {
                "sessionid": records[0]['sessionid'],
                "severity": records[0]['severity'],
                "category": records[0]['category'],
                "mark_as_complete": records[0]['mark_as_complete'],
                "chatsummary": records[0]['chatsummary'],
                "chattranscript": records[0]['chattranscript'],
                "comments": [
                    {
                        "comment_id": record['comment_id'],
                        "comment": record['comment'],
                        "email": record['email']
                    }
                    for record in records
                    if record['comment_id'] is not None
                ],
            }
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{sid}/comments")
async def add_comment_to_session(sid: UUID, comment: Comment, email: str, auth_result: str = Security(auth.verify)):
    insert_query = """
    INSERT INTO comments (sessionid, comment, email)
    VALUES ((SELECT sessionid FROM chatrecords WHERE sessionid = $1), $2, $3)
    RETURNING comment_id
    """
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
async def update_chat_urgency(sid: UUID, urgency: str, auth_result: str = Security(auth.verify)):
    update_query = """
    UPDATE chatrecords
    SET severity = $1
    WHERE sessionid = $2
    """
    try:
        conn = await get_connection()
        result = await conn.execute(update_query, urgency, sid)
        await conn.close()
        if result == 'UPDATE 1':
            return {"message": "Chat urgency updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update-chat-team")
async def update_chat_team(sid: UUID, team: str, auth_result: str = Security(auth.verify)):
    update_query = """
    UPDATE chatrecords
    SET category = $1, triaging_confirmed = True
    WHERE sessionid = $2
    """
    try:
        conn = await get_connection()
        result = await conn.execute(update_query, team, sid)
        await conn.close()
        if result == 'UPDATE 1':
            return {"message": "Chat team updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/take-action")
async def take_action(sid: UUID, action_taken_notes: str, mark_as_complete: bool,
                      auth_result: str = Security(auth.verify)):
    update_query = """
    UPDATE chatrecords
    SET action_taken_notes = $1, mark_as_complete = $2
    WHERE sessionid = $3
    """
    try:
        conn = await get_connection()
        result = await conn.execute(update_query, action_taken_notes, mark_as_complete, sid)
        await conn.close()
        if result == 'UPDATE 1':
            return {"message": "Action taken successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
