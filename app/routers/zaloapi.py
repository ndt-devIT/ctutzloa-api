import httpx
import os
import base64
import hashlib
import uuid

from fastapi import APIRouter, Body, HTTPException
from datetime import datetime

from app.core.config import APP_ID, APP_SECRET, REDIRECT_URI
from app.models.zaloPKCE import ZaloPKCE
from app.models.zaloToken import ZaloToken
from app.models.zaloFollowers import ZaloFollower

from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/zalo", tags=["Zalo"])


# ==============================
# PKCE GENERATOR
# ==============================
async def get_valid_access_token():

    token = await ZaloToken.find_one()

    if not token:
        raise HTTPException(400, "Chưa có token Zalo OA")

    # kiểm tra token hết hạn
    if token.expiredAt and token.expiredAt < datetime.utcnow():
        raise HTTPException(401, "Access token đã hết hạn, cần tạo lại")

    return token.accessToken

def generate_pkce():

    code_verifier = base64.urlsafe_b64encode(
        os.urandom(40)
    ).decode().rstrip("=")

    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    return code_verifier, code_challenge


# ==============================
# STEP 1: AUTH URL
# ==============================

@router.get("/auth-url")
async def zalo_auth_url():

    code_verifier, code_challenge = generate_pkce()
    state = str(uuid.uuid4())

    pkce = ZaloPKCE(
        state=state,
        codeVerifier=code_verifier
    )

    await pkce.insert()

    url = (
        "https://oauth.zaloapp.com/v4/oa/permission"
        f"?app_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
    )

    return {"auth_url": url}


# ==============================
# EXCHANGE TOKEN
# ==============================

async def get_access_token(code: str, code_verifier: str):

    async with httpx.AsyncClient() as client:

        res = await client.post(
            "https://oauth.zaloapp.com/v4/oa/access_token",
            headers={
                "secret_key": APP_SECRET,
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "app_id": APP_ID,
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier
            }
        )

        data = res.json()

        if "access_token" not in data:
            return data

        # ==============================
        # XÓA TOKEN CŨ NẾU TỒN TẠI
        # ==============================
        old_token = await ZaloToken.find_one()

        if old_token:
            await old_token.delete()

        # ==============================
        # LƯU TOKEN MỚI
        # ==============================
        token = ZaloToken(
            accessToken=data["access_token"],
            refreshToken=data.get("refresh_token"),
            expiresIn=data.get("expires_in"),
            expiredAt=datetime.utcnow()
        )

        await token.insert()

        return data


# ==============================
# CALLBACK
# ==============================

from fastapi.responses import HTMLResponse

@router.get("/callback", response_class=HTMLResponse)
async def zalo_callback(code: str, state: str):

    pkce = await ZaloPKCE.find_one(ZaloPKCE.state == state)

    if not pkce:
        return HTMLResponse("""
        <h3>OAuth Error</h3>
        <p>Invalid state</p>
        """)

    code_verifier = pkce.codeVerifier

    await pkce.delete()

    token = await get_access_token(code, code_verifier)

    html = f"""
    <html>
    <head>
        <title>Zalo OAuth</title>
    </head>
    <body style="font-family:sans-serif;text-align:center;margin-top:50px;">
        <h3>✔ Zalo OA Authorization Success</h3>
        <p>Popup sẽ tự đóng...</p>

        <script>

            const token = {token};

            if (window.opener) {{
                window.opener.postMessage({{
                    type: "zalo-oauth-success",
                    token: token
                }}, "*")
            }}

            setTimeout(() => {{
                window.close()
            }}, 1000)

        </script>

    </body>
    </html>
    """

    return HTMLResponse(html)


# ==============================
# GET ACCESS TOKEN
# ==============================

async def get_valid_access_token():

    token = await ZaloToken.find_one(
        sort=[("createdAt", -1)]
    )

    if not token:
        raise HTTPException(
            status_code=400,
            detail="Chưa authorize OA."
        )

    return token.accessToken


# ==============================
# GET FOLLOWERS
# ==============================

@router.get("/followers")
async def get_followers(offset: int = 0, count: int = 50):

    access_token = await get_valid_access_token()

    async with httpx.AsyncClient() as client:

        res = await client.get(
            "https://openapi.zalo.me/v2.0/oa/getfollowers",
            headers={
                "access_token": access_token
            },
            params={
                "data": f'{{"offset":{offset},"count":{count}}}'
            }
        )

        data = res.json()

        return data
    
@router.post("/sync-followers")
async def sync_followers(user_ids: List[str] = Body(...)):

    access_token = await get_valid_access_token()

    results = []

    async with httpx.AsyncClient() as client:

        for user_id in user_ids:

            res = await client.get(
                "https://openapi.zalo.me/v2.0/oa/getprofile",
                headers={
                    "access_token": access_token
                },
                params={
                    "data": f'{{"user_id":"{user_id}"}}'
                }
            )

            profile = res.json()

            if profile.get("error") != 0:
                continue

            p = profile["data"]

            # kiểm tra đã tồn tại chưa
            follower = await ZaloFollower.find_one(ZaloFollower.userId == p["user_id"])

            if follower:

                follower.displayName = p.get("display_name")
                follower.avatar = p.get("avatar")
                follower.avatars = p.get("avatars")
                follower.gender = p.get("user_gender")
                follower.birthDate = p.get("birth_date")
                follower.isSensitive = p.get("is_sensitive")
                follower.updatedAt = datetime.utcnow()

                await follower.save()

            else:

                follower = ZaloFollower(
                    userId=p["user_id"],
                    userIdByApp=p.get("user_id_by_app"),
                    displayName=p.get("display_name"),
                    avatar=p.get("avatar"),
                    avatars=p.get("avatars"),
                    gender=p.get("user_gender"),
                    birthDate=p.get("birth_date"),
                    isSensitive=p.get("is_sensitive"),
                )

                await follower.insert()

            results.append(p)

    return {
        "synced": len(results),
        "data": results
    }