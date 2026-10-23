import os
from pathlib import Path


class Settings:
    """Runtime configuration,全部可用环境变量覆盖。"""

    APP_NAME: str = "三国杀移动版盒子模拟器"
    API_PREFIX: str = "/api"

    # 数据库
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "/app/data"))
    DB_FILE: str = os.getenv("DB_FILE", "sanguosha.db")

    # 鉴权
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sanguosha-box-simulator-dev-secret-change-me")
    ALGORITHM: str = "HS256"
    TOKEN_EXPIRE_HOURS: int = int(os.getenv("TOKEN_EXPIRE_HOURS", "168"))

    # 数值
    INITIAL_YUANBAO: int = int(os.getenv("INITIAL_YUANBAO", "8888"))
    MAX_BULK_OPEN: int = int(os.getenv("MAX_BULK_OPEN", "50"))
    RECHARGE_STEP: int = int(os.getenv("RECHARGE_STEP", "1000"))

    # 数据目录（只读卡池配置）
    DATA_FILES: Path = Path(__file__).parent / "data"

    # 素材目录（武将/皮肤/道具图），默认取项目根的 image/
    IMAGE_DIR: Path = Path(
        os.getenv("IMAGE_DIR", str(Path(__file__).resolve().parents[2] / "image"))
    )

    @property
    def database_url(self) -> str:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.DATA_DIR / self.DB_FILE}"


settings = Settings()
