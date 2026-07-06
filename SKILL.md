---
name: yjs-cdp-scraper
description: >
  Batch search and filter job listings on yingjiesheng.com via Edge CDP
  (Chrome DevTools Protocol). Use when the user asks to search jobs, filter
  by keyword/city on 应届生求职网, extract job listings for analysis, or
  batch scrape from yingjiesheng.com. Architecture: Edge Browser
  (--remote-debugging-port=9222) <-> Python CDP WebSocket client <-> Page JS
  extraction. Requires `pip install websocket-client` and Edge running with
  remote debugging enabled.
---

# 应届生求职网 CDP 批量岗位筛选

## 架构

```
用户 ─── 应届生求职网 (Edge浏览器) ─── CDP (port 9222) ─── Python脚本 (WebSocket)
                                                              │
                                                      搜索 → 提取 → 翻页 → 筛选 → 导出
                                                              │
                                                        JSON / CSV 文件
```

## 快速开始

### 1. 启动 Edge 调试模式

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

然后手动打开 https://q.yingjiesheng.com 并登录。

### 2. 安装依赖

```bash
pip install websocket-client
```

### 3. 运行

```bash
# 基础搜索
python scripts/cdp_scraper.py --keyword "水电工" --city "上海"

# 带筛选
python scripts/cdp_scraper.py --keyword "管培生" --city "北京" --exclude "实习,兼职"

# 导出CSV
python scripts/cdp_scraper.py --keyword "数据分析" --format csv -o results.csv
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keyword` / `-k` | 搜索关键词 (必填) | - |
| `--city` / `-c` | 城市筛选 | 不限 |
| `--include` / `-i` | 标题包含关键词(逗号分隔) | - |
| `--exclude` / `-e` | 排除关键词(逗号分隔) | - |
| `--max-pages` / `-p` | 最大翻页数 | 5 |
| `--output` / `-o` | 输出文件路径 | 自动生成 |
| `--format` / `-f` | json / csv | json |
| `--port` | CDP 调试端口 | 9222 |

## 工作原理

1. **连接**: Python 通过 `http://localhost:9222/json/list` 检测 Edge CDP 端口，找到应届生求职网标签页
2. **导航**: 通过 `Page.navigate` 构建搜索 URL 并导航
3. **提取**: 通过 `Runtime.evaluate` 在页面注入 JS 提取岗位卡片
4. **翻页**: JS 点击"下一页"按钮，循环提取直到达到 `--max-pages`
5. **筛选**: Python 侧按关键词/城市/排除词过滤
6. **导出**: 输出 JSON 或 CSV 文件

## 故障排查

**CDP 端口未开启**:
```powershell
# 关闭所有 Edge 进程
taskkill /F /IM msedge.exe
# 重新启动带调试端口
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

**找不到标签页**: 确保 q.yingjiesheng.com 已在 Edge 中打开（非 job_detail 页面）

**页面提取不到数据**: 站点可能改版。在 Edge 控制台运行诊断:
```js
document.querySelectorAll("div, li").forEach((el, i) => {
    if (el.children.length >= 3 && el.textContent.length > 50 && el.textContent.length < 500) {
        console.log(i, el.className, el.textContent.substring(0, 100));
    }
});
```
