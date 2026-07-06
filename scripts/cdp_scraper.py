#!/usr/bin/env python3
"""
应届生求职网 CDP 批量岗位筛选工具
=============================================
架构: Edge浏览器 (远程调试端口9222) ← CDP WebSocket → Python脚本

前置条件:
    Edge 浏览器以远程调试模式启动:
    msedge --remote-debugging-port=9222

用法:
    # 搜索并提取
    python cdp_scraper.py --keyword "水电工" --city "上海"

    # 搜索并筛选
    python cdp_scraper.py --keyword "数据分析" --city "北京" --exclude "实习,兼职"

    # 导出CSV
    python cdp_scraper.py --keyword "管培生" --format csv
"""
import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.request
from collections import OrderedDict

try:
    import websocket
except ImportError:
    print("请安装 websocket-client: pip install websocket-client")
    sys.exit(1)

BASE_URL = "https://www.yingjiesheng.com/"
SEARCH_URL = "https://q.yingjiesheng.com/pc/search"
CDP_PORT = 9222
CDP_HOST = f"http://localhost:{CDP_PORT}"


class CDPClient:
    """Chrome DevTools Protocol 客户端"""

    def __init__(self, port=9222):
        self.port = port
        self.host = f"http://localhost:{port}"
        self.ws = None
        self._msg_id = 0
        self._timeout = 10

    def _next_id(self):
        self._msg_id += 1
        return self._msg_id

    def _connect_tab(self, tab_id=None):
        """连接到指定 tab 或找到应届生求职网 tab"""
        if tab_id:
            ws_url = f"ws://localhost:{self.port}/devtools/page/{tab_id}"
        else:
            tabs = self.list_tabs()
            yjs_tab = None
            for t in tabs:
                if "yingjiesheng.com" in t.get("url", "") and "job_detail" not in t.get("url", ""):
                    yjs_tab = t
                    break
            if not yjs_tab:
                raise RuntimeError("未找到应届生求职网标签页")
            ws_url = yjs_tab["webSocketDebuggerUrl"]
            print(f"连接 tab: {yjs_tab.get('title', 'N/A')}")

        socket.setdefaulttimeout(self._timeout)
        self.ws = websocket.create_connection(ws_url, timeout=self._timeout)
        self._drain_messages()
        self.send("Runtime.enable")

    @staticmethod
    def list_tabs():
        """列出所有打开的标签页"""
        try:
            with urllib.request.urlopen(f"{CDP_HOST}/json/list") as resp:
                return json.loads(resp.read())
        except Exception:
            return []

    @staticmethod
    def check_port():
        """检查 CDP 端口是否可用"""
        try:
            with urllib.request.urlopen(f"{CDP_HOST}/json/version", timeout=3) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    def _drain_messages(self):
        """排空待处理消息"""
        self.ws.settimeout(0.5)
        try:
            while True:
                self.ws.recv()
        except Exception:
            pass
        self.ws.settimeout(self._timeout)

    def send(self, method, params=None, timeout=None):
        """发送 CDP 命令并等待响应"""
        msg_id = self._next_id()
        cmd = {"id": msg_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(cmd))

        if timeout:
            self.ws.settimeout(timeout)

        while True:
            data = json.loads(self.ws.recv())
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP Error: {data['error']}")
                return data.get("result", {})
            elif "method" in data:
                continue

        if timeout:
            self.ws.settimeout(self._timeout)

    def evaluate(self, js_code, await_promise=False):
        """在页面中执行 JavaScript"""
        params = {
            "expression": js_code,
            "returnByValue": True,
        }
        if await_promise:
            params["awaitPromise"] = True
        result = self.send("Runtime.evaluate", params)
        value = result.get("result", {}).get("value")
        if isinstance(value, str):
            return value
        return value

    def navigate(self, url):
        """导航到指定 URL"""
        self.send("Page.navigate", {"url": url})
        time.sleep(2)
        self._drain_messages()

    def close(self):
        if self.ws:
            self.ws.close()


class YJSJobScraper:
    """应届生求职网岗位筛选器"""

    def __init__(self, port=9222):
        self.cdp = CDPClient(port)

    def connect(self):
        """连接并验证"""
        info = CDPClient.check_port()
        if not info:
            raise RuntimeError(
                f"Edge 远程调试端口 {CDP_PORT} 未开启。\n"
                "请用以下命令启动 Edge:\n"
                '  msedge --remote-debugging-port=9222'
            )
        print(f"已连接 Edge ({info.get('Browser', 'Unknown')})")
        self.cdp._connect_tab()
        return self

    def search(self, keyword, city="", max_pages=5):
        """搜索岗位并翻页提取"""
        params = f"keyword={urllib.parse.quote(keyword)}"
        if city:
            params += f"&city={urllib.parse.quote(city)}"

        url = f"{SEARCH_URL}?{params}"
        print(f"搜索: {keyword} {city or '(不限城市)'}")
        self.cdp.navigate(url)
        time.sleep(3)

        all_jobs = []
        for page in range(1, max_pages + 1):
            print(f"提取第 {page} 页...")
            js_result = self.cdp.evaluate("""
(function() {
    var results = [];
    var cards = document.querySelectorAll(
        '.job-list-item, .job-item, .list-item, [class*=joblist] li, [class*=job-list] li, [class*=jobItem], [class*=job]'
    );
    if (!cards.length) {
        var all = document.querySelectorAll('div, li, tr');
        cards = Array.from(all).filter(function(el) {
            var t = el.textContent;
            return (t.indexOf('K') !== -1 || t.indexOf('元') !== -1) &&
                   el.children.length >= 3;
        });
    }
    cards.forEach(function(card, idx) {
        var text = card.textContent || '';
        var title = '', company = '', salary = '', location = '';
        var el = card.querySelector('a[href*=job], h3, h4, .job-title, [class*=title], [class*=name]');
        if (el) title = el.textContent.trim();
        el = card.querySelector('.company, .corp, [class*=company]');
        if (el) company = el.textContent.trim();
        var m = text.match(/(\\d+[-~]\\d+[Kk])|(\\d+元[/ ]*[天日月年])/);
        if (m) salary = m[0];
        m = text.match(/([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼][\\u4e00-\\u9fa5]{0,4}(?:市|区|县))/);
        if (m) location = m[0];
        results.push({idx: idx, title: title, company: company, salary: salary, location: location});
    });
    return JSON.stringify({count: cards.length, jobs: results});
})();
""", await_promise=False)

            try:
                page_data = json.loads(js_result)
                jobs_on_page = page_data.get("jobs", [])
                all_jobs.extend(jobs_on_page)
                print(f"  获取 {len(jobs_on_page)} 个岗位 (累计 {len(all_jobs)})")
            except json.JSONDecodeError:
                print("  解析失败，跳过此页")
                break

            # 翻页
            if page < max_pages:
                next_ok = self.cdp.evaluate("""
(function() {
    var btn = document.querySelector('.next, [class*=next], .pagination .next, a:last-child');
    if (btn && !btn.classList.contains('disabled')) {
        btn.click();
        return 'ok';
    }
    return 'no_next';
})();
""")
                if next_ok == 'no_next':
                    print("  没有下一页，停止翻页")
                    break
                time.sleep(2)

        return all_jobs

    def filter_jobs(self, jobs, include="", exclude="", city=""):
        """筛选岗位"""
        include_kw = [k.strip() for k in include.split(",") if k.strip()]
        exclude_kw = [k.strip() for k in exclude.split(",") if k.strip()]

        filtered = []
        for j in jobs:
            text = f"{j.get('title','')} {j.get('company','')}"
            if include_kw and not any(k in text for k in include_kw):
                continue
            if exclude_kw and any(k in text for k in exclude_kw):
                continue
            if city and city not in (j.get("location", "") or ""):
                continue
            filtered.append(j)
        return filtered

    def export(self, jobs, output_path, fmt="json"):
        """导出结果"""
        if fmt == "csv":
            import csv
            with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["title", "company", "salary", "location"])
                writer.writeheader()
                writer.writerows(jobs)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"total": len(jobs), "jobs": jobs}, f, ensure_ascii=False, indent=2)

        print(f"已导出 {len(jobs)} 个岗位 -> {output_path}")

    def close(self):
        self.cdp.close()


def main():
    parser = argparse.ArgumentParser(description="应届生求职网 CDP 批量岗位筛选")
    parser.add_argument("--keyword", "-k", required=True, help="搜索关键词")
    parser.add_argument("--city", "-c", default="", help="城市")
    parser.add_argument("--include", "-i", default="", help="包含关键词(逗号分隔)")
    parser.add_argument("--exclude", "-e", default="", help="排除关键词(逗号分隔)")
    parser.add_argument("--max-pages", "-p", type=int, default=5, help="翻页数")
    parser.add_argument("--output", "-o", default="", help="输出路径")
    parser.add_argument("--format", "-f", default="json", choices=["json", "csv"])
    parser.add_argument("--port", type=int, default=9222, help="CDP端口")
    args = parser.parse_args()

    scraper = YJSJobScraper(port=args.port)

    try:
        scraper.connect()
        jobs = scraper.search(args.keyword, args.city, args.max_pages)

        if args.include or args.exclude or args.city:
            jobs = scraper.filter_jobs(jobs, args.include, args.exclude, args.city)
            print(f"筛选后: {len(jobs)} 个岗位")

        # 打印摘要
        for j in jobs[:15]:
            print(f"  {j['title']} | {j['company']} | {j['salary']} | {j.get('location','')}")
        if len(jobs) > 15:
            print(f"  ... 共 {len(jobs)} 个")

        # 导出
        output = args.output or f"yjs_{args.keyword}_{args.city or 'all'}.{args.format}"
        scraper.export(jobs, output, args.format)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
