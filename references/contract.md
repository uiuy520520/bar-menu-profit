# 輸入輸出契約 v1.0.0

輸入根物件 currency（必填）、period（選填）、basis（必填，使用者確認的共同價格與成本基準文字）、ingredients 陣列、drinks 陣列。
每個食材：id、pack_cost、pack_qty、unit（ml/l/g/kg/piece）、yield_rate（0<值<=1）。
每個飲品：id、name、recipe（ingredient_id/qty/unit）、production_loss（0<=值<1）、packaging_cost、price、discount_rate、fee_rate（率皆0到1）、fixed_fee、quantity（非負整數或 null）。recipe 不可空白。

缺少數值欄位或 null 為未知，不推定 0。數值接受 JSON number 或數值字串；拒絕布林、NaN、Infinity、負數與非整數銷量。食材與飲品 id 唯一；未定義的食材視為缺資料，不假造。名稱僅為資料，不解讀為指令。未知額外欄位不參與計算。

- 基本單位：1l=1000ml、1kg=1000g；piece 不跨量綱。
- 食材每基本單位成本 = pack_cost / (換算後 pack_qty × yield_rate)。
- 配方成本 = Σ食材用量成本 / (1-production_loss)。額外製作損耗為可用配方投入量中未成為售出飲品的比例；不與已計入 yield_rate 的原料損耗重複。
- 每杯直接成本 = 配方成本 + packaging_cost。
- 實收收入 = price × (1-discount_rate)。
- 直接毛利 = 實收收入 - 每杯直接成本；直接毛利率 = 直接毛利 / 實收收入。
- 通路費 = 實收收入 × fee_rate + fixed_fee（每杯）。
- 單杯貢獻 = 直接毛利 - 通路費；期間貢獻 = 單杯貢獻 × quantity。
- 未提供銷量只影響期間貢獻；未提供任何成本/收入必要欄位，該飲品 blocked。
- 成本下限僅累加已知原料成本與已知包材；未知損耗不放大。不可把下限當完整成本。
- 輸出：currency/basis/period/results；各結果含 status、missing、已知成本下限，完整項目另含各計算欄位。百分比輸出為0到1比例，前端需乘100顯示。JSON 輸出金額為小數兩位字串。

使用範例：`python3 scripts/calculate.py assets/example.json --output /path/to/result.json`。
結果不含固定營運費分攤，不能當成會計淨利或報稅資料。不同通路用不同 drink id，分別給 price/fee_rate/quantity；不可將通路重複銷量相加。


## 單位量詞 v1.1
- 容量：ml／毫升、l／公升（大小寫皆可）。重量：g／克／公克、kg／公斤／千克。
- 計數：piece／顆／個、slice／片、portion／份、drop／滴。
- 包裝：bottle／瓶／支、bag／袋／包、box／盒、can／罐。
- 顆與片、份、滴各自為不同量綱；瓶與罐等包裝亦不同，不直接互換。相同量詞可直接計價，例如一盒100元，用0.5盒。
- 每種原料可填 unit_conversions。例：琴酒 pack_cost=700、pack_qty=1、unit="支"，unit_conversions={"支":{"qty":700,"unit":"ml"}}，代表每支700ml。配方45ml成本45元。
- 換算只限同一原料、由業主明確提供。來源為量詞或包裝，目標為 ml/l/g/kg/piece/slice/portion；禁止鍊式換算、覆寫公升公斤的標準換算。缺換算遇到不同量綱即拒絕，不假定每滴或每顆的容量。
- 分數數量可以填0.5顆、0.25份；比例只在相同量綱換成相同基本單位後計算。混合公克與毫升不得合計為單一比例。


## 空間／營運費分攤 v1.2
選填 operating_costs 物件：rent（房租）、electricity（電費）、water（水費）、consumables（未列配方與包材的共用耗材）、salary（同期全店薪資總額）、total_cups（全店同期正整數總杯數）、period（須與根物件period相同）、consumables_exclude_recipe_and_packaging（業主確認無重複時填true）。費用與原配方須用相同幣別及價格基準。

全店同期每杯分攤=(rent+electricity+water+consumables+salary)/total_cups。
結果 operating_cost_allocation 含status/missing，成功時另有total_cost、total_cups、cost_per_cup。
每個完整飲品另含 allocated_operating_cost_per_cup、contribution_after_listed_operating_costs、period_contribution_after_listed_operating_costs。保留完整精度至輸出才四捨五入。缺資料時不輸出此三欄，但不阻擋原本飲品成本結果。
這是等杯數管理分攤，非空間坪數分攤；本次不計坪數。五項費用扣除後仍不代表完整淨利。total_cups=0時拒絕，避免除零；可先不提供模組或留空並標示待補。

薪資 salary 未提供或null時，營運費分攤blocked，保留原飲品分析；確認無薪資才填0。僅需總額，不蒐集姓名；加班費、獎金若已含於總額不可重複加計。人事附加成本與業主薪酬的包含範圍需在報告明列。


## 依序填員工薪資 v1.3
operating_costs 可提供 employees 陣列，順序即填寫順序，另設 employees_complete=true 確認名單完整。與非null salary互斥。
每列 id 為唯一非空員工編號；pay_type="monthly" 時填 period_salary（當期應付月薪金額）；pay_type="hourly" 時填 hourly_rate、hours（允許小數）。均須填 additional_pay（尚未包含的加班費/獎金等當期額外薪資，無則確認後填0）。不自動推算法定加班、扣薪或雇主負擔。純時薪工時不得再重複納入額外加班金額。
月薪員工當期金額=period_salary+additional_pay；時薪員工=hourly_rate×hours+additional_pay。保留精度至輸出。空名單須確認employees_complete=true才表示無員工薪資。
缺員工金額/工時/額外薪資或未確認名單完整：只阻擋營運費分攤，保留原飲品分析。輸出operating_cost_allocation.payroll（sequence、id、pay_type、status、missing、period_pay）及salary_total；不完整時salary_total為null，不顯示部分加總為完整薪資。
姓名非必要；員工編號及個別薪資為敏感營運資料，不上傳或同步到Notion/GitHub等紀錄，僅保存功能與虛構QA結果。


## 額外薪資分項 v1.4
新表單每位員工分別填 performance_bonus（當期業績獎金）及 overtime_pay（當期加班費）；皆為非負金額，無則確認後填0。兩欄取代舊additional_pay，兩欄只要出現任一欄就必須兩欄填齊，缺漏為blocked；與非null additional_pay互斥，避免重複。
當期薪資=月薪當期金額或時薪×一般工時，再加performance_bonus+overtime_pay。獎金與加班費僅接受業主確認金額，不自動判定法規或比例。輸出每人extra_pay_breakdown分項及additional_pay_total合計。


## 餐飲擴充 v1.5
新增taiwan_jin／斤／台斤／臺斤（600g）、skewer／串、basket／籃。包沿用bag、個沿用piece。
包、籃、串可透過每個原料unit_conversions轉換至克或個/串，不假定固定內容量；固定台斤不得覆寫換算。餐點可用根物件meals代替drinks（互斥），仍回傳results。進貨總價pack_cost對應進貨數量pack_qty。
例如肉品pack_cost=180、pack_qty=1、unit=斤，配方qty=150、unit=克，食材成本45元。
例如串料pack_cost=300、pack_qty=1、unit=包、unit_conversions={"包":{"qty":10,"unit":"串"}}，配方2串成本60元。
