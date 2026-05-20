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


@contextmanager
def proxy_context(proxy_url: str = None):
    """
    [网络隔离 - 正向]
    临时启用代理设置，完成后恢复。
    适用于：需要代理才能访问的数据源（如 AkShare 连接东方财富获取 PE 数据）。
    """
    # 如果没有提供代理 URL，从环境变量读取
    if proxy_url is None:
        proxy_url = (
            os.environ.get('http_proxy') or 
            os.environ.get('https_proxy') or 
            os.environ.get('HTTP_PROXY') or 
            os.environ.get('HTTPS_PROXY')
        )
    
    if not proxy_url:
        # 没有代理配置，直接执行（不报错）
        yield
        return
    
    # 备份可能存在的代理设置
    proxy_vars = [
        'http_proxy', 'https_proxy', 'all_proxy', 
        'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'
    ]
    env_backup = {}
    for k in proxy_vars:
        if k in os.environ:
            env_backup[k] = os.environ[k]
    
    # 设置代理
    os.environ['http_proxy'] = proxy_url
    os.environ['https_proxy'] = proxy_url
    
    try:
        yield
    finally:
        # 恢复原状
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        os.environ.pop('all_proxy', None)
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('ALL_PROXY', None)
        for k, v in env_backup.items():
            os.environ[k] = v