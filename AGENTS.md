ILANG
[TYPE:agent-guide][PROJECT:vps-deals][LANG:zh]

::STATE{@PROJECT, kind:static_coupon_asset, niche:VPS hosting deals}

::MODULE{PURPOSE}
  这是一个零服务器的静态优惠垂直站。数据来自公开的厂商页面、sitemap 或 feed。
  运行链路是 scraper.py 抓取公开事实，build.py 生成 site/，GitHub Actions 定时更新并提交。

::MODULE{BOUNDARY}
  允许: 增加真实厂商入口 改模板 改解析规则 改站点文案 改联盟裸链映射。
  禁止: 编优惠 编价格 编佣金 绕过 robots.txt 抓登录内容 注入 cookie 或伪造有效期。

::MODULE{INVARIANTS}
  抓不到 price 就不写 price 字段，也不写进结构化数据。
  valid_until 已过就标 expired，结构化数据用 OutOfStock 并且不写 priceValidUntil。
  每页必须有自指 canonical 和 JSON-LD；og 图由 build.py 生成，不要手写。

::MODULE{CONFIG}
  .ilang/site.ilang 是站点配置唯一真源。
  scraper.py 和 build.py 都必须从该文件读取品牌、细分、域名和厂商清单。
  判据: 改 site.ilang 里一家厂商，重跑 scraper.py 加 build.py，site/ 就该变。

::MODULE{OPERATIONS}
  本地更新: python scraper.py 然后 python build.py。
  部署: Cloudflare Pages 构建命令 python build.py，输出目录 site/。
  运行时零 API 密钥 零推理 零第三方依赖，只用 Python 标准库。
