from fastapi import APIRouter

# `/v1`, not `/v1/account`: the photo of any account is served at `/v1/accounts/{id}/photo`.
router = APIRouter(prefix="/v1", tags=["account"])
