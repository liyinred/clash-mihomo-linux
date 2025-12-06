# Linux 安装 Clash 内核并开启透明代理

## 下载 Clash [​](#下载-clash)

### Clash 内核 [​](#clash-内核)

1.  Clash 内核分为 [开源版](https://github.com/Dreamacro/clash/releases) / [Premium 版](https://github.com/Dreamacro/clash/releases/tag/premium)(已删库) / [Meta 版(mihomo)](https://github.com/MetaCubeX/mihomo/releases) ，可以根据需求自行选择版本
2.  在 release 中下载对应系统的内核解压后，重命名为 `clash` 上传至 `/opt/clash`
3.  执行 `chmod +x /opt/clash/clash` 添加运行权限

```sh
mkdir -p /opt/clash && cd /opt/clash && \
wget -O mihomo.gz https://github.com/MetaCubeX/mihomo/releases/latest/download/mihomo-linux-amd64-compatible-v1.19.10.gz && \
gunzip mihomo.gz && chmod +x mihomo
```

### Country.mmdb [​](#country-mmdb)

在 [maxmind-geoip](https://github.com/Dreamacro/maxmind-geoip/releases) 中下载全球 IP 库 Country.mmdb 文件上传至 `/opt/clash`

```sh
wget -O /opt/clash/Country.mmdb https://github.com/Dreamacro/maxmind-geoip/releases/latest/download/Country.mmdb
```

### 控制面板 [​](#控制面板)

在 [metacubexd](https://github.com/MetaCubeX/metacubexd/releases) 中下载面板文件上传至 `/opt/clash/ui`

```sh
mkdir -p /opt/clash/ui && cd /opt/clash/ui && \
wget https://github.com/MetaCubeX/metacubexd/releases/latest/download/compressed-dist.tgz && \
tar -xzf compressed-dist.tgz && rm compressed-dist.tgz
```

### config.yaml [​](#config-yaml)

- 将配置文件命名为 `config.yaml` 上传至 `/opt/clash`

```sh
wget -O /opt/clash/config.yaml https://domain.com/clash.yaml
```

- 在配置文件中，除了常规的节点规则配置以外，确保包含**外部控制**配置

```yaml
external-controller: 0.0.0.0:9090
external-ui: /opt/clash/ui
secret: ""
```

## 创建 systemd 配置文件 [​](#创建-systemd-配置文件)

1.  创建 systemd 配置文件

/etc/systemd/system/clash.service

```ini
[Unit]
Description=Clash 守护进程, Go 语言实现的基于规则的代理.
After=network.target NetworkManager.service systemd-networkd.service iwd.service

[Service]
Type=simple
LimitNPROC=500
LimitNOFILE=1000000
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE CAP_SYS_TIME
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW CAP_NET_BIND_SERVICE CAP_SYS_TIME
Restart=always
ExecStartPre=/usr/bin/sleep 1s
ExecStart=/opt/clash/mihomo -d /opt/clash
ExecReload=/bin/kill -HUP $MAINPID

[Install]
WantedBy=multi-user.target
```

2.  重新加载 systemd

```sh
systemctl daemon-reload
```

3.  接下来就可以通过 systemctl 控制 Clash 启动与停止

```sh
systemctl status clash # 运行状态
systemctl start clash # 启动
systemctl stop clash # 停止
systemctl enable clash # 开机自启
systemctl disable clash # 取消开机自启
```

4.  查看日志可以通过 `journalctl`

```sh
journalctl -u clash --reverse
```

## 系统代理 [​](#系统代理)

1.  创建并编辑 `.bashrc`

2.  将以下代码写入其中

```sh
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
export all_proxy="socks5://127.0.0.1:7890"
export no_proxy="localhost,127.*,10.*,172.16.*,172.17.*,172.18.*,172.19.*,172.20.*,172.21.*,172.22.*,172.23.*,172.24.*,172.25.*,172.26.*,172.27.*,172.28.*,172.29.*,172.30.*,172.31.*,192.168.*"

source ~/.bashrc
```

## TUN 模式 [​](#tun-模式)

### 开启流量转发 [​](#开启流量转发)

1.  编辑 `/etc/sysctl.conf` 文件

2.  将以下代码取消注释

```txt
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
```

3.  加载内核参数

### 开启 dns [​](#开启-dns)

提示

2025 年 3 月之后，海外 DoH / DoT 都被屏蔽了

如需使用，要通过 `https://8.8.8.8/dns-query#proxy` 这样的形式或启用 fake-ip

如不使用 DoH / DoT 则不受影响，正常使用 `8.8.8.8` 这种形式即可

1.  53 端口可能被占用，关闭默认的系统 dns 端口

```sh
systemctl disable systemd-resolved
```

2.  在 Clash 配置文件中添加 dns

```yaml
dns:
  enable: true
  prefer-h3: true
  ipv6: true
  listen: 0.0.0.0:53
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  fake-ip-filter:
    - controlplane.tailscale.com
    - log.tailscale.io
  nameserver:
    - https://223.5.5.5/dns-query#h3=true
    - https://223.6.6.6/dns-query#h3=true
    - tls://223.5.5.5
    - tls://223.6.6.6
  fallback:
    - https://8.8.8.8/dns-query
    - https://8.8.4.4/dns-query
    - https://1.1.1.1/dns-query
    - https://1.0.0.1/dns-query
    - tls://8.8.8.8
    - tls://8.8.4.4
    - tls://1.1.1.1
    - tls://1.0.0.1
```

### 开启 TUN [​](#开启-tun)

提示

如果将设备作为**旁路网关**，需要将网关和 DNS 都指向该设备，并且关闭**终端设备**的 IPv6（Android 需要 Root）

否则 IPv6 流量可能不会经过指定的 IPv4 网关，更多问题建议参考 [ShellCrash 的常见问题](https://juewuy.github.io/chang-jian-wen-ti/#%E7%BD%91%E7%BB%9C%E7%9B%B8%E5%85%B3%E9%97%AE%E9%A2%98)解决

在 Clash 配置文件中添加 TUN

```yaml
tun:
  enable: true
  stack: mixed
  auto-route: true
  auto-redirect: true
  auto-detect-interface: true
  dns-hijack:
    - any:53
    - tcp://any:53
```
