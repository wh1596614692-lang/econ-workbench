"""Small-instance deployment configuration, read once when the server starts."""
import os


def positive_int(name, default, maximum):
    value = int(os.environ.get(name, str(default)))
    if not 1 <= value <= maximum:
        raise ValueError(f'{name} must be between 1 and {maximum}.')
    return value


MODE = os.environ.get('ECON_DEPLOYMENT_MODE', 'local')
if MODE not in {'local', 'cloud'}:
    raise ValueError('ECON_DEPLOYMENT_MODE must be local or cloud.')
MAX_SESSIONS = positive_int('ECON_MAX_SESSIONS', 12, 100)
MAX_CONCURRENT_JOBS = positive_int('ECON_MAX_CONCURRENT_JOBS', 2, 8)
SESSION_DATA_MB = positive_int('ECON_SESSION_DATA_MB', 200, 4096)
TOTAL_DATA_MB = positive_int('ECON_TOTAL_DATA_MB', 1200, 16384)


def public_settings():
    cloud = MODE == 'cloud'
    return {
        'deployment_mode': MODE,
        'processing_location': 'server' if cloud else 'local',
        'privacy_notice': (
            '文件上传到本网站服务器计算；按浏览器会话隔离，不发送至 AI 服务。'
            '闲置两小时或服务重启后清除，请及时导出。请勿上传不允许交给网站运营者处理的数据。'
            if cloud else
            '数据在本机服务中计算，不发送至 AI 服务；闲置两小时或服务停止后清除。'
        ),
        'max_sessions': MAX_SESSIONS,
        'max_concurrent_jobs': MAX_CONCURRENT_JOBS,
    }
