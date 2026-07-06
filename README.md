# 应届生求职网 CDP 批量岗位筛选工具

> 通过 Edge 浏览器远程调试协议 (CDP)，实现在 [应届生求职网](https://q.yingjiesheng.com) 上批量搜索、提取、筛选和导出岗位信息。

## 🏗️ 架构

```
┌──────────┐     CDP:9222      ┌──────────────────┐
│  用户     │─── WebSocket ───▶│  Python 脚本      │
│  (Edge)   │                   │  cdp_scraper.py   │
└──────────┘                   └──────┬───────────┘
                                      │
                          搜索 → 提取 → 翻页 → 筛选 → 导出
                                      │
                              ┌───────┴───────┐
                              │  JSON / CSV   │
                              └───────────────┘
```

## 🚀 快速开始

### 前提条件

- Windows 系统，Edge 浏览器已安装
- Python 3.8+

### 1. 启动 Edge 调试模式

```powershell
# 关闭所有 Edge 进程
taskkill /F /IM msedge.exe

# 带远程调试端口启动
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

然后手动打开 https://q.yingjiesheng.com 并登录你的账号。

### 2. 安装依赖

```bash
pip install websocket-client
```

### 3. 运行

```bash
# 基础搜索
python scripts/cdp_scraper.py --keyword "水电工" --city "上海"

# 带筛选条件
python scripts/cdp_scraper.py --keyword "管培生" --city "北京" --exclude "实习,兼职" --format csv

# 搜索更多页
python scripts/cdp_scraper.py --keyword "软件开发" --max-pages 10 -o dev_jobs.json
```

## 📋 参数说明

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--keyword` | `-k` | 搜索关键词 (**必填**) | - |
| `--city` | `-c` | 城市筛选 | 不限 |
| `--include` | `-i` | 标题包含关键词 (逗号分隔) | - |
| `--exclude` | `-e` | 排除关键词 (逗号分隔) | - |
| `--max-pages` | `-p` | 最大翻页数 | 5 |
| `--output` | `-o` | 输出文件路径 | 自动生成 |
| `--format` | `-f` | 输出格式: `json` / `csv` | json |
| `--port` | | CDP 调试端口 | 9222 |

## 📦 输出示例

### JSON 格式
```json
{
  "total": 30,
  "jobs": [
    {
      "idx": 0,
      "title": "水电工程师",
      "company": "某建筑工程有限公司",
      "salary": "8-12K",
      "location": "上海"
    }
  ]
}
```

### CSV 格式
| title | company | salary | location |
|-------|---------|--------|----------|
| 水电工程师 | 某建筑工程有限公司 | 8-12K | 上海 |

## 🔧 工作原理

1. **连接检测** — 通过 `http://localhost:9222/json/version` 检测 Edge CDP 是否就绪
2. **标签定位** — 通过 `http://localhost:9222/json/list` 找到应届生求职网标签页
3. **页面导航** — 通过 CDP `Page.navigate` 构建搜索 URL 并跳转
4. **数据提取** — 通过 CDP `Runtime.evaluate` 在页面注入 JS 提取岗位卡片
5. **自动翻页** — JS 点击"下一页",循环直到达到 `--max-pages` 或无更多页
6. **本地筛选** — Python 侧按关键词/城市/排除词进行二次过滤
7. **文件导出** — 输出为 JSON 或 CSV (UTF-8 BOM, Excel 直接打开不乱码)

## 🐛 故障排查

### CDP 端口未开启
```powershell
# 检查端口
netstat -ano | findstr 9222

# 如果没有输出，重新启动 Edge
taskkill /F /IM msedge.exe
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

### 找不到标签页
确保 `q.yingjiesheng.com` 已在 Edge 中打开（不是岗位详情页 `jobdetail`）

### 提取不到数据 (站点改版)
在 Edge 控制台 (F12) 运行以下诊断脚本，观察实际的 DOM 结构：

```js
document.querySelectorAll("div, li").forEach((el, i) => {
    if (el.children.length >= 3 && el.textContent.length > 50 && el.textContent.length < 500) {
        console.log(i, el.className, el.textContent.substring(0, 100));
    }
});
```

将观察到的 class 名称更新到 `cdp_scraper.py` 的 `search()` 方法中的选择器列表。

## ⚠️ 注意事项

- **反爬保护**: 应届生求职网使用阿里云 WAF，必须通过真实浏览器访问
- **登录状态**: Edge 的登录 Cookie 会被 CDP 连接复用，无需额外处理
- **请求频率**: 每次翻页间隔 2 秒，避免触发风控
- **Edge 版本**: 已知兼容 Edge 149+

## 📄 License

MIT
