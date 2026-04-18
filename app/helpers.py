import os
import uuid

from PIL import Image
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp']

def allowed_file(file_name):
    if '.' not in file_name:
        return False
    ext = file_name.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def save_image(file_storage, upload_folder):
    if file_storage is None or file_storage.filename == '':
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError('Можно загружать только png, jpg, jpeg или webp.')

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    original_name = secure_filename(file_storage.filename)
    ext = original_name.rsplit('.', 1)[1].lower()
    file_name = str(uuid.uuid4()) + '.' + ext
    full_path = os.path.join(upload_folder, file_name)

    image = Image.open(file_storage)
    image = image.convert('RGB')
    image.thumbnail((320, 220))
    image.save(full_path, quality=90)

    return 'uploads/' + file_name

def remove_image(upload_folder, image_path):
    if image_path is None:
        return

    if image_path == 'images/picture.png':
        return

    if not str(image_path).startswith('uploads/'):
        return

    file_name = str(image_path).replace('uploads/', '')
    full_path = os.path.join(upload_folder, file_name)

    if os.path.exists(full_path):
        os.remove(full_path)