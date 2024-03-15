import json
import os
import random
import string

import aiohttp


async def generate_password(length=12):
    while True:
        password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=length))
        if (any(c.islower() for c in password) and 
                any(c.isupper() for c in password) and 
                any(c in string.punctuation for c in password)):
            return password


async def _get_user_roles(sid):
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
            return await response.text(), json_data.get('access_token')


async def create_name_to_id_mapping_async(data):
    return {item['name']: item['id'] for item in data}


async def fetch_id_by_name_async(name_to_id_mapping, name):
    return name_to_id_mapping.get(name)


async def fetch_role_id(role, token):
    async with aiohttp.ClientSession() as session:
        url = f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/roles"
        payload = {}
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        async with session.get(url, headers=headers) as response:
            name_to_id_mapping = await create_name_to_id_mapping_async(await response.json())
            found_id = await fetch_id_by_name_async(name_to_id_mapping, role)
            return found_id
