from fastapi import FastAPI, HTTPException, Query, Depends, Header
from pydantic import BaseModel, Field
import asyncpg
from asyncpg.exceptions import UniqueViolationError
from uuid import UUID
from typing import List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

app = FastAPI()
load_dotenv(dotenv_path='.venv/.env')
# Define your API keys
API_KEYS = {
    "Jatin": "ab_lE7ZQVFxUGnLaRu5KmD1JvnYFOTCPLwM",
    "Ahsan": "ab_dmjos9J0Z4zabmIpx8BFviNctENf2ls6"
}


def verify_api_key(api_key: str = Header(None)):
    """
    Verify the API key.

    Args:
        api_key (str, optional): The API key to verify. Defaults to None.

    Returns:
        str: The verified API key.

    Raises:
        HTTPException: If the API key is invalid.

    Example:
        >>> verify_api_key(api_key="abc123")
        "abc123"
    """

    if api_key is None or api_key not in API_KEYS.values():
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


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


@app.get("/users-data")
async def get_users_data(team: Optional[str] = None, search: Optional[str] = None, page: Optional[int] = Query(1, ge=1),
                         limit: Optional[int] = Query(10, le=100), api_key: str = Depends(verify_api_key)):
    select_query = """
    SELECT name, emailorphonenumber, datetimeofchat, severity, socialcareeligibility, status
    FROM chatrecords
    """
    conditions = []
    if team:
        conditions.append(f"category = '{team}'")
    if search:
        conditions.append(f"name ILIKE '%{search}%'")
    if conditions:
        select_query += " WHERE " + " AND ".join(conditions)

    select_query += f" ORDER BY datetimeofchat DESC LIMIT {limit} OFFSET {(page - 1) * limit}"

    try:
        conn = await get_connection()
        records = await conn.fetch(select_query)
        await conn.close()
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{id}")
async def get_session_by_id(sid: UUID, api_key: str = Depends(verify_api_key)):
    select_query = """
    SELECT chatsummary, chattranscript
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
async def update_chat_urgency(sid: UUID, urgency: str, api_key: str = Depends(verify_api_key)):
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
async def update_chat_team(sid: UUID, team: str, api_key: str = Depends(verify_api_key)):
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
async def take_action(sid: UUID, action_taken_notes: str, mark_as_complete: bool,
                      api_key: str = Depends(verify_api_key)):
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
