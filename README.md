# POUR｜餐飲與酒吧成本管理

內附操作介面的獨立 Skill，支援食材與酒材進貨、餐點與飲品配方、單位換算、月薪/時薪人員、業績獎金與加班費，以及房租、水電、耗材與薪資分攤。

## 啟動介面

需要 Python 3，無第三方套件。

```bash
python scripts/serve_ui.py
```

開啟 http://127.0.0.1:8765/ 。按 Ctrl+C 結束。

## 命令列計算與驗證

```bash
python scripts/calculate.py assets/example.json --output result.json
python -m unittest discover -s tests -v
```

根目錄 SKILL.md 為技能入口。範例與測試資料均為虛構，不代表真實店家、員工薪資或市場報價。未列入費用不包含於結果，並非完整淨利。

## 隱私

表單預設空白，無外部追蹤與遠端資料上傳。資料只送往本機計算服務；選擇本機儲存時使用未加密的瀏覽器localStorage。勿於共用裝置保存個別薪資；請勿將真實薪資、配方、匯出檔或憑證提交至版本庫。

## 驗證限制

59項本機單元與整合測試通過；尚未完成新版介面瀏覽器視覺驗證及實店資料驗收。
