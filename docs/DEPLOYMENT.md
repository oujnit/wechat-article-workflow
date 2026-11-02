# 固定出口部署与新电脑迁移

本地负责写作，服务器负责访问微信接口。先核实服务器对外出口 IP，把实际出口加入所属公众号后台白名单。不要把文档示例当成真实部署值。

## 初始化

1. 自行准备可访问微信接口的固定出口服务器。
2. 使用专用 SSH 用户，在本机 SSH 配置中设置自选别名，如 `publisher`；核对主机指纹，私钥留在 SSH 配置目录。
3. 服务器准备 Python 3 与 venv，把本仓库部署到专用目录，例如 `/srv/wechat-workflow`，在该目录 `.venv` 安装 requirements.txt。
4. 在项目目录外创建仅部署用户可读的环境文件，例如 `/srv/wechat-config/publisher.env`，填入 WECHAT_APPID、WECHAT_SECRET、可选 WECHAT_AUTHOR，权限 600。不要提交真实值。
5. 服务器依赖和环境文件由拥有者管理，不用脚本从其他项目搜索或复制凭据。

```bash
export WECHAT_REMOTE_HOST=publisher
export WECHAT_REMOTE_ROOT=/srv/wechat-workflow
export WECHAT_REMOTE_ENV=/srv/wechat-config/publisher.env
./scripts/remote.sh sync work/my-article/article.json
```

服务器需有 `.venv/bin/python`。`remote.sh` 的 create/update 使用固定根目录下的此解释器加载指定环境文件后执行；sync 不加载配置、不调用微信。远端路径限制为常规绝对路径以避免误解析。

## 同步规则

只同步 publisher.py、该篇清单、HTML、封面和本地正文图，保留原有相对目录。不镜像删除整个远端目录，不上传 `.env`、私钥和本地回执。真实回执在远端第一次运行后生成，后续修订沿用它。

服务器备份应覆盖私有回执与 work 素材，按私有数据保护。需要拉回回执时，用 SSH 安全复制到本机被忽略的 work 目录，不放进示例或公共问题反馈。新电脑接手不能用空回执覆盖服务器回执。

## 本地直连

publisher.py 可以在配置好环境后直接运行 create/update，但调用机器的出口必须满足微信后台白名单。固定出口部署优先。本仓库没有复用早期依赖临时文件和本地动态 IP 的 shell 推送链路。

正式接入前核对[官方接口说明](https://developers.weixin.qq.com/doc/offiaccount/Getting_Started/Overview.html)。离线测试通过不表示账号已获得接口权限或服务器白名单已放行。
