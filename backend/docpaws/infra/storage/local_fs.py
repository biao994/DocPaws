"""
本地文件存储：上传/读取/删除

接口稳定，未来可替换为 S3/MinIO/OSS。
"""
import hashlib
import os
from uuid import uuid4

from docpaws.settings import settings


class LocalStorage:
    """本地文件系统存储"""

    async def save_upload_to_temp_and_hash(self, upload_file, *, chunk_size: int = 1024 * 1024) -> tuple[str, str, int]:
        """
        将 UploadFile 流式写入临时文件，并同时计算 sha256 与 size。

        Returns:
            (temp_path, sha256, size_bytes)
        """
        temp_path = os.path.join(settings.UPLOAD_DIR, f"temp_{uuid4().hex}")
        sha256_obj = hashlib.sha256()
        size = 0
        with open(temp_path, "wb") as f:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                sha256_obj.update(chunk)
                size += len(chunk)
        return temp_path, sha256_obj.hexdigest(), size

    def move_temp_to_storage(self, temp_path: str, filename: str, *, file_object_id: str | None = None) -> str:
        """
        将临时文件移动为正式存储路径（同盘 rename）。

        Returns:
            storage_path
        """
        fid = file_object_id or uuid4().hex
        safe_name = os.path.basename(filename)
        storage_path = os.path.join(settings.UPLOAD_DIR, f"{fid}_{safe_name}")
        os.rename(temp_path, storage_path)
        return storage_path

    def delete_if_unreferenced(self, storage_path: str) -> bool:
        """删除未被引用的物理文件"""
        if not storage_path or not os.path.exists(storage_path):
            return False
        try:
            os.remove(storage_path)
            return True
        except OSError:
            return False

    def exists(self, path: str) -> bool:
        return os.path.exists(path)


storage = LocalStorage()
