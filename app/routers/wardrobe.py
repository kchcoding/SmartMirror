"""옷장 관리 API (폰에서 사진 업로드)."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..database import list_clothes
from ..services import wardrobe as wardrobe_service

router = APIRouter(prefix="/api/wardrobe", tags=["wardrobe"])


@router.get("")
def get_clothes():
    return list_clothes()


@router.post("")
async def upload_clothing(
    name: str = Form(...),
    category: str = Form(...),          # top | bottom | outer
    color: str = Form("검정"),
    warmth: int = Form(3),              # 1~5
    waterproof: bool = Form(False),
    image: UploadFile = File(...),
):
    content = await image.read()
    try:
        new_id = wardrobe_service.save_upload(name, category, color, warmth, waterproof, image.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": new_id}


@router.delete("/{clothing_id}")
def delete_clothing(clothing_id: int):
    if not wardrobe_service.remove(clothing_id):
        raise HTTPException(status_code=404, detail="없는 옷이에요")
    return {"ok": True}
