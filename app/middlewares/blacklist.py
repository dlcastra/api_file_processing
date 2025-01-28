from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class BlacklistMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis):
        super().__init__(app)
        self.redis = redis
        self.logout_url = "/logout"

    async def dispatch(self, request: Request, call_next):
        session_id = request.session.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")

        key = f"blacklist:session:{session_id}"
        is_blacklisted = self.redis.exists(key)
        if is_blacklisted:
            request.session.clear()

        response = await call_next(request)
        return response
