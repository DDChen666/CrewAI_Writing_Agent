"""Utilities for interacting with the Reddit Data API via OAuth2."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests


class RedditOAuthClient:
    """Simple client that authenticates using the client credentials flow."""

    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    API_BASE_URL = "https://oauth.reddit.com"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout: int = 10,
    ) -> None:
        self.client_id = client_id or os.environ.get("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Reddit OAuth client credentials are not configured")

        self.user_agent = user_agent or os.environ.get(
            "REDDIT_USER_AGENT", "CrewAI Reddit Scraper/1.0"
        )
        self.timeout = timeout

        session = requests.Session()
        session.trust_env = False
        self._session = session

        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _token_is_valid(self) -> bool:
        return bool(self._access_token and time.time() < self._token_expiry - 30)

    def _request_token(self) -> None:
        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        headers = {"User-Agent": self.user_agent}
        data = {"grant_type": "client_credentials"}
        response = self._session.post(
            self.TOKEN_URL,
            headers=headers,
            data=data,
            auth=auth,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in

    def _ensure_token(self) -> str:
        if not self._token_is_valid():
            self._request_token()
        assert self._access_token is not None
        return self._access_token

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        url = endpoint if endpoint.startswith("http") else f"{self.API_BASE_URL}{endpoint}"
        max_attempts = 3
        backoff_seconds = 1.0
        refresh_attempted = False
        last_exception: Optional[Exception] = None
        response: Optional[requests.Response] = None

        for attempt in range(max_attempts):
            try:
                token = self._ensure_token()
                headers = {
                    "Authorization": f"bearer {token}",
                    "User-Agent": self.user_agent,
                }

                response = self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    timeout=timeout or self.timeout,
                )

                if response.status_code == 401 and not refresh_attempted:
                    refresh_attempted = True
                    self._request_token()
                    continue

                if response.status_code in {429} or response.status_code >= 500:
                    if attempt < max_attempts - 1:
                        time.sleep(backoff_seconds)
                        backoff_seconds *= 2
                        continue

                response.raise_for_status()
                return response
            except requests.RequestException as exc:  # pragma: no cover - network issues
                last_exception = exc
                if attempt < max_attempts - 1:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                raise

        if response is not None:
            response.raise_for_status()
            return response
        assert last_exception is not None
        raise last_exception

    def request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        response = self.request(
            method,
            endpoint,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
        )
        return response.json()

    def get(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        final_params = dict(params or {})
        final_params.setdefault("raw_json", 1)
        return self.request_json("GET", endpoint, params=final_params, timeout=timeout)

    def post(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        return self.request_json(
            "POST",
            endpoint,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
        )
