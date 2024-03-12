import json
import os
import random
import string

import aiohttp


async def _generate_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(length))
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
