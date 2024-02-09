from fastapi import FastAPI, HTTPException, Query, Depends, Header
from pydantic import BaseModel, Field
import asyncpg
from asyncpg.exceptions import UniqueViolationError
from uuid import UUID
from typing import List, Optional
from datetime import datetime
import os
import json
import requests
import http.client
from dotenv import load_dotenv

app = FastAPI()
load_dotenv(dotenv_path='.venv/.env')
# Define your API keys

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


async def get_connection():

    return await asyncpg.connect(user=os.getenv('PGUSER'), password=os.getenv('PGPASSWORD'),
                                 database=os.getenv('PGDATABASE'), host=os.getenv('PGHOST'))


@app.get("/")
async def health_check():

    return {"message": "FastAPI application is running"}


@app.get("/get_roles")
async def get_user_roles(sid):

    conn = http.client.HTTPSConnection(os.getenv('DOMAIN'))

    payload = ("{\"client_id\":" + f"\"{os.getenv('CLIENT_ID')}\"" +
               ",\"client_secret\":" + f"\"{os.getenv('CLIENT_SECRET')}\"" +
               ",\"audience\":" + f"\"https://{os.getenv('DOMAIN')}/api/v2/\"" +
               ",\"grant_type\":\"client_credentials\"}")

    headers = {'content-type': "application/json"}

    conn.request("POST", "/oauth/token", payload, headers)

    response = conn.getresponse()
    response_data = response.read().decode('utf-8')
    # Parse the JSON data
    # print(response_data)
    json_data = json.loads(response_data)
    url = f"https://dev-3cph6dxaz67l2bm7.us.auth0.com/api/v2/users/{sid}/roles"

    payload = {}

    headers = {
        'Accept': 'application/json',
        'Authorization': f"Bearer {json_data.get('access_token')}"
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    return response.text



@app.get("/users-data")
async def get_users_data(team: Optional[str] = None, search: Optional[str] = None, page: Optional[int] = Query(1, ge=1),
                         limit: Optional[int] = Query(10, le=100)):
    count_query = """
    SELECT COUNT(*) FROM chatrecords
    """
    select_query = """
    SELECT sessionid, name, emailorphonenumber, datetimeofchat, severity, socialcareeligibility, mark_as_complete, category
    FROM chatrecords
    """
    conditions = []
    if team:
        conditions.append(f"category = '{team}'")
    if search:
        conditions.append(f"name ILIKE '%{search}%'")
    if conditions:
        select_query += " WHERE " + " AND ".join(conditions)
        count_query += " WHERE " + " AND ".join(conditions)

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
async def get_session_by_id(sid: UUID):
    select_query = """
    SELECT sessionid, severity, category, mark_as_complete, chatsummary, chattranscript
    FROM chatrecords
    WHERE sessionid = $1
    """
    try:
        conn = await get_connection()
        record = await conn.fetchrow(select_query, sid)
        await conn.close()
        if record:
            return record
        else:
            raise HTTPException(status_code=404, detail="Session ID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update-chat-urgency")
async def update_chat_urgency(sid: UUID, urgency: str):
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
async def update_chat_team(sid: UUID, team: str):
    update_query = """
    UPDATE chatrecords
    SET category = $1
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
async def take_action(sid: UUID, action_taken_notes: str, mark_as_complete: bool):
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
