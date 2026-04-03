import argparse
import re
import sys
import time
import urllib.parse
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString


DEFAULT_SUBSCRIPTION_URL = (
    "https://liangxin.xyz/api/v1/liangxin?OwO=7b11b17dc07fe232514a6bbc561f5253"
)
DEFAULT_TEMPLATE_URL = (
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/"
    "ACL4SSR_Online_Mini.ini"
)
DEFAULT_CONVERTER_BASE = "https://api.wcc.best/sub"
REQUIRED_KEYS = ("proxies", "proxy-groups", "rules")
DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3


def build_converter_url(
    subscription_url: str,
    converter_base: str = DEFAULT_CONVERTER_BASE,
    template_url: str = DEFAULT_TEMPLATE_URL,
) -> str:
    query = urllib.parse.urlencode(
        {
            "target": "clash",
            "url": subscription_url,
            "insert": "false",
            "config": template_url,
        }
    )
    return f"{converter_base}?{query}"


def build_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/yaml,text/plain,*/*",
        "Connection": "close",
    }


def fetch_with_requests(url: str, timeout: int) -> str:
    response = requests.get(url, headers=build_headers(), timeout=timeout)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> str:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return fetch_with_requests(url, timeout)
        except Exception as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(attempt)
    raise RuntimeError(f"请求转换链接失败，已重试 {retries} 次: {last_error}")


def normalize_remote_yaml(text: str) -> str:
    # Some unquoted short-id values such as `6314e825` are misparsed as floats.
    return re.sub(
        r"(?P<prefix>short-id:\s*)(?P<value>[^\s,}\]]+)",
        lambda match: f'{match.group("prefix")}"{match.group("value")}"',
        text,
    )


def load_remote_sections(text: str) -> dict:
    text = normalize_remote_yaml(text)
    yaml = YAML(typ="safe")
    data = yaml.load(text)
    if not isinstance(data, dict):
        raise ValueError("转换接口返回的内容不是有效的 Clash YAML 对象")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"转换结果缺少必要字段: {', '.join(missing)}")

    return {key: data[key] for key in REQUIRED_KEYS}


def force_string_scalars(sections: dict) -> None:
    for proxy in sections.get("proxies", []):
        if not isinstance(proxy, dict):
            continue

        reality_opts = proxy.get("reality-opts")
        if isinstance(reality_opts, dict) and "short-id" in reality_opts:
            reality_opts["short-id"] = DoubleQuotedScalarString(
                str(reality_opts["short-id"])
            )


def update_config(config_path: Path, sections: dict, backup: bool = True) -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.allow_unicode = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=2, offset=0)

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.load(file)

    if not isinstance(config, dict):
        raise ValueError(f"{config_path} 不是有效的 YAML 映射对象")

    force_string_scalars(sections)

    for key in REQUIRED_KEYS:
        config[key] = sections[key]

    if backup:
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        backup_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=config_path.parent,
        suffix=".tmp",
    ) as temp_file:
        yaml.dump(config, temp_file)
        temp_path = Path(temp_file.name)

    temp_path.replace(config_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过订阅链接更新当前目录下 config.yaml 的 proxies、proxy-groups、rules 字段。"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_SUBSCRIPTION_URL,
        help="订阅链接，默认使用脚本内置测试链接。",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="要更新的 Clash 配置文件路径，默认是当前目录下的 config.yaml。",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="不生成 config.yaml.bak 备份文件。",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        print(f"未找到配置文件: {config_path}", file=sys.stderr)
        return 1

    converter_url = build_converter_url(args.url)
    try:
        remote_text = fetch_text(converter_url)
        sections = load_remote_sections(remote_text)
        update_config(config_path, sections, backup=not args.no_backup)
    except Exception as exc:
        print(f"更新失败: {exc}", file=sys.stderr)
        return 1

    print("----")
    print(f"已更新 {config_path}")
    print("----")
    print(f"转换链接: {converter_url}")
    print("----")
    print(
        "字段统计: "
        f"proxies={len(sections['proxies'])}, "
        f"proxy-groups={len(sections['proxy-groups'])}, "
        f"rules={len(sections['rules'])}"
    )
    print("----")
    print("proxies 列表:")
    for index, proxy in enumerate(sections["proxies"], start=1):
        proxy_name = proxy.get("name", "<unnamed>") if isinstance(proxy, dict) else str(proxy)
        print(f"{index}. {proxy_name}")
    print("----")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
