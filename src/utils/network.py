# src/utils/network.py

import os
import logging
import urllib.request
from contextlib import contextmanager

@contextmanager
def no_proxy_context():
    """
    [网络隔离舱]
    临时屏蔽系统代理设置（含环境变量和注册表），
    确保代码块内的请求强制直连。
    适用于：在开启全局代理的电脑上，强行直连国内数据源（如腾讯/东财）。
    """
    # 1. 备份并清除环境变量
    proxy_vars = [
        'http_proxy', 'https_proxy', 'all_proxy', 
        'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'
    ]
    env_backup = {}
    for k in proxy_vars:
        if k in os.environ:
            env_backup[k] = os.environ[k]
            os.environ.pop(k, None)
    
    # 设置 NO_PROXY 为通配符
    os.environ['NO_PROXY'] = '*'
    
    # 2. [关键] Monkey Patch: 屏蔽 Windows 注册表读取
    # 防止 requests/urllib 读取 IE 代理设置
    original_getproxies = urllib.request.getproxies
    urllib.request.getproxies = lambda: {}

    # logging.debug("🛡️ [网络隔离] 已启用：屏蔽代理与注册表")
    
    try:
        yield
    finally:
        # 3. 恢复现场
        urllib.request.getproxies = original_getproxies
        os.environ.pop('NO_PROXY', None)
        for k, v in env_backup.items():
            os.environ[k] = v
        # logging.debug("🔄 [网络隔离] 已解除")