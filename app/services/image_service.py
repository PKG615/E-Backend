import os
import uuid
from typing import List, Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from app.models.product import Product, ProductImage
from app.schemas.product import (
    ProductImageCreate, 
    ProductImageUpdate, 
    ProductImageReorderRequest
)

# Upload configuration
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "products")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_image_bytes(content: bytes) -> bool:
    """Validate image magic bytes to strictly prevent executable or malicious files."""
    if len(content) < 8:
        return False
    # JPEG
    if content.startswith(b"\xff\xd8\xff"):
        return True
    # PNG
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # GIF
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return True
    # WEBP: "RIFF....WEBP"
    if content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
        return True
    return False


def get_product_or_404(product_id: int, db: Session) -> Product:
    """Fetch product or raise a 404 exception."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    return product


def get_product_images(product_id: int, db: Session) -> List[ProductImage]:
    """Retrieve all images for a product in deterministic order (sort_order ASC, id ASC)."""
    get_product_or_404(product_id, db)
    return db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).order_by(
        asc(ProductImage.sort_order),
        asc(ProductImage.id)
    ).all()


def add_product_image(
    product_id: int, 
    payload: ProductImageCreate, 
    db: Session
) -> ProductImage:
    """
    Add an image to a product transactionally.
    Enforces primary image rules and sort_order calculation.
    """
    get_product_or_404(product_id, db)
    
    # Check existing images count and primary state
    existing_images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    has_primary = any(img.is_primary for img in existing_images)
    
    is_primary = payload.is_primary
    # If this is the first image, or if explicitly requested as primary, make it primary
    if not existing_images or (not has_primary and not payload.is_primary):
        is_primary = True

    # If new image is primary, transactionally unset primary for all existing images
    if is_primary:
        db.query(ProductImage).filter(
            ProductImage.product_id == product_id
        ).update({"is_primary": False})

    # Determine sort_order
    sort_order = payload.sort_order
    if sort_order == 0 and existing_images:
        max_order = max((img.sort_order for img in existing_images), default=0)
        sort_order = max_order + 1
    
    display_order = payload.display_order if payload.display_order is not None else sort_order

    new_image = ProductImage(
        product_id=product_id,
        image_url=payload.image_url.strip(),
        alt_text=payload.alt_text.strip() if payload.alt_text else None,
        is_primary=is_primary,
        sort_order=sort_order,
        display_order=display_order
    )

    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    return new_image


async def upload_product_image(
    product_id: int,
    file: UploadFile,
    alt_text: Optional[str],
    is_primary: bool,
    sort_order: int,
    db: Session
) -> ProductImage:
    """
    Safely process, validate, save and register an uploaded product image.
    """
    get_product_or_404(product_id, db)

    # Validate filename & extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename"
        )
    
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Validate Content-Type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type '{file.content_type}'. Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    # Read content and validate size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Validate magic bytes
    if not validate_image_bytes(content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a valid image format"
        )

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Generate safe unique filename
    unique_filename = f"prod_{product_id}_{uuid.uuid4().hex[:12]}{ext}"
    destination_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(destination_path, "wb") as f:
        f.write(content)

    public_url = f"/uploads/products/{unique_filename}"

    create_payload = ProductImageCreate(
        image_url=public_url,
        alt_text=alt_text,
        is_primary=is_primary,
        sort_order=sort_order if sort_order >= 0 else 0
    )

    return add_product_image(product_id=product_id, payload=create_payload, db=db)


def update_product_image(
    product_id: int, 
    image_id: int, 
    payload: ProductImageUpdate, 
    db: Session
) -> ProductImage:
    """
    Update image attributes with strict product ownership verification.
    """
    get_product_or_404(product_id, db)
    
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID {image_id} not found"
        )
    
    if image.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image with ID {image_id} does not belong to Product {product_id}"
        )

    if payload.image_url is not None:
        image.image_url = payload.image_url.strip()
    
    if payload.alt_text is not None:
        image.alt_text = payload.alt_text.strip() if payload.alt_text else None
    
    if payload.sort_order is not None:
        image.sort_order = payload.sort_order
        image.display_order = payload.sort_order
    elif payload.display_order is not None:
        image.sort_order = payload.display_order
        image.display_order = payload.display_order

    if payload.is_primary is not None:
        if payload.is_primary:
            # Unset any other primary
            db.query(ProductImage).filter(
                ProductImage.product_id == product_id,
                ProductImage.id != image_id
            ).update({"is_primary": False})
            image.is_primary = True
        else:
            image.is_primary = False

    db.commit()
    db.refresh(image)
    return image


def set_primary_image(product_id: int, image_id: int, db: Session) -> ProductImage:
    """
    Transactionally designate an image as the product's primary image.
    old primary -> false
    new primary -> true
    """
    get_product_or_404(product_id, db)
    
    target_image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not target_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID {image_id} not found"
        )
    
    if target_image.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image with ID {image_id} does not belong to Product {product_id}"
        )

    # Transaction: reset old primary, set new primary
    db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).update({"is_primary": False})

    target_image.is_primary = True
    db.commit()
    db.refresh(target_image)
    return target_image


def reorder_product_images(
    product_id: int, 
    payload: ProductImageReorderRequest, 
    db: Session
) -> List[ProductImage]:
    """
    Transactionally update sort order of product images.
    Deterministic ordering: sort_order ASC, id ASC.
    """
    get_product_or_404(product_id, db)
    
    existing_images = db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).all()
    image_dict = {img.id: img for img in existing_images}

    if payload.image_ids is not None:
        # Validate all provided IDs belong to this product
        for img_id in payload.image_ids:
            if img_id not in image_dict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image ID {img_id} does not belong to product {product_id}"
                )
        # Apply sequential sort_order
        for index, img_id in enumerate(payload.image_ids):
            img = image_dict[img_id]
            img.sort_order = index
            img.display_order = index

    elif payload.items is not None:
        for item in payload.items:
            if item.id not in image_dict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image ID {item.id} does not belong to product {product_id}"
                )
            img = image_dict[item.id]
            img.sort_order = item.sort_order
            img.display_order = item.sort_order
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'image_ids' or 'items' must be provided for reordering"
        )

    db.commit()
    return get_product_images(product_id, db)


def delete_product_image(product_id: int, image_id: int, db: Session) -> bool:
    """
    Safely delete a product image.
    If the deleted image was primary, automatically promotes the next available image.
    """
    get_product_or_404(product_id, db)
    
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID {image_id} not found"
        )
    
    if image.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image with ID {image_id} does not belong to Product {product_id}"
        )

    was_primary = image.is_primary
    file_path_to_clean = None
    if image.image_url.startswith("/uploads/products/"):
        file_path_to_clean = os.path.join(os.getcwd(), image.image_url.lstrip("/"))

    db.delete(image)
    db.flush()

    # If deleted image was primary, pick the lowest sort_order image as new primary
    if was_primary:
        next_primary = db.query(ProductImage).filter(
            ProductImage.product_id == product_id
        ).order_by(
            asc(ProductImage.sort_order),
            asc(ProductImage.id)
        ).first()

        if next_primary:
            next_primary.is_primary = True

    db.commit()

    # Clean up local file if exists
    if file_path_to_clean and os.path.exists(file_path_to_clean):
        try:
            os.remove(file_path_to_clean)
        except Exception:
            pass

    return True
