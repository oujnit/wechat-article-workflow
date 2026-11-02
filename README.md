# WeChat Article Workflow

微信公众号文章生产、校对、配图、排版和草稿发布的脱敏工作流。适合在本地与 AI 协作写稿，再通过固定出口服务器创建或更新草稿。

这是从实际项目文件与历史会话整理的通用版本，包含流程、可运行的虚构示例和离线测试。不包含原公众号身份、真实文章、聊天原文、服务器地址、密钥、已上传图片地址或真实草稿回执。历史新闻案例没有作为当前事实重新发布。

## 完整链路

选题 → 一手来源核验 → 明确文章主线 → 中文初稿 → 配图与图注 → 内联样式 → 本地检查与手机预览 → 同步固定出口服务器 → 上传素材 → 创建/更新草稿 → 回读核验 → 保存私有回执。

正式发表与群发是独立步骤。本工具只操作草稿；历史项目的正式发布接口曾返回权限不足，不能据此承诺所有账号都能通过 API 正式发表。

## 本地演示

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/inline_css.py examples/demo/article.html examples/demo/article.inline.html
python scripts/publisher.py check examples/demo/article.json
python -m unittest discover -s tests -v
python scripts/privacy_check.py
```

`check` 不读取公众号凭据、不调用微信接口。演示文字和图形均为虚构素材，不能当作新闻。

## 实际使用

复制示例到忽略目录 `work/一篇文章/`，替换文章、封面和正文图，修改清单中的相对路径、摘要与回执位置。先做本地检查，用户明确要求创建或覆盖草稿后才执行写入。

```bash
python scripts/publisher.py check work/my-article/article.json
export WECHAT_REMOTE_HOST=publisher
./scripts/remote.sh sync work/my-article/article.json
./scripts/remote.sh create work/my-article/article.json
# 同一草稿的修订：清单仍使用原来的 receipt
./scripts/remote.sh update work/my-article/article.json
```

服务器单独配置 `WECHAT_APPID`、`WECHAT_SECRET`，作者 `WECHAT_AUTHOR` 可不填。运行环境加载方法与服务器初始化见 [部署说明](docs/DEPLOYMENT.md)。不要把真实配置填入仓库里的示例。

## 文档入口

| 文档 | 内容 |
|---|---|
| [历史会话总结](docs/SESSION_REVIEW.md) | 记录范围、流程演进、教训和证据限制 |
| [完整操作流程](docs/WORKFLOW.md) | 选题、核验、写作、配图、草稿、正式发表与贴图 |
| [文风与排版](STYLE_DNA.md) | 自然中文、事实边界、紧凑移动端样式 |
| [部署与迁移](docs/DEPLOYMENT.md) | 固定出口、SSH、凭据、同步与回执保护 |
| [异常恢复](docs/RECOVERY.md) | 网络中断、重复稿、过期 ID、编码、白名单 |
| [脱敏记录](docs/PRIVACY.md) | 公开内容边界、扫描方式与旧脚本处置 |
| [交给其他 AI](AGENTS.md) | 接手规则 |

本次验证覆盖离线检查、模拟接口和隐私扫描；公开模板未连接真实公众号执行发布。微信接口权限、字段限制、上传要求和编辑器行为需按使用时的[微信官方文档](https://developers.weixin.qq.com/doc/offiaccount/Getting_Started/Overview.html)核实。
