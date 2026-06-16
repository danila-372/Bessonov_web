import hashlib
import uuid
import os
from werkzeug.utils import secure_filename
from flask import current_app
from app.models import Image

class ImageRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, image_id):
        return self.db.session.get(Image, image_id)

    def add_image(self, file):
        self.img = self.__find_by_md5_hash(file)
        if self.img is not None:
            return self.img
        file_name = secure_filename(file.filename)
        self.img = Image(
            id=str(uuid.uuid4()),
            file_name=file_name,
            mime_type=file.mimetype,
            md5_hash=self.md5_hash
        )
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], self.img.storage_filename))
        self.db.session.add(self.img)
        self.db.session.commit()
        return self.img

    def __find_by_md5_hash(self, file):
        self.md5_hash = hashlib.md5(file.read()).hexdigest()
        file.seek(0)
        return self.db.session.execute(self.db.select(Image).filter(Image.md5_hash == self.md5_hash)).scalar()
