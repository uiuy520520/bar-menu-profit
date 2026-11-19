#!/usr/bin/env python3
"""Deterministic per-drink costing; no network, third-party dependencies, or tax inference."""
import argparse
import json
import sys
import os
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

UNITS={'ml':('volume',1),'l':('volume',1000),'g':('mass',1),'kg':('mass',1000),'piece':('count',1), 'slice':('slice',1), 'portion':('portion',1), 'drop':('drop',1), 'bottle':('bottle',1), 'bag':('bag',1), 'box':('box',1), 'can':('can',1),'taiwan_jin':('mass',600),'skewer':('skewer',1),'basket':('basket',1)}
ALIASES={'毫升':'ml','公升':'l','克':'g','公克':'g','公斤':'kg','千克':'kg','顆':'piece','個':'piece','片':'slice','份':'portion','滴':'drop','瓶':'bottle','支':'bottle','袋':'bag','包':'bag','盒':'box','罐':'can','斤':'taiwan_jin','台斤':'taiwan_jin','臺斤':'taiwan_jin','串':'skewer','籃':'basket'}

def number(value, name, maximum=None, positive=False, exclusive=False):
    if value is None:
        return None
    if len(str(value))>100:
        raise ValueError(name+': number too long')
    if isinstance(value,bool):
        raise ValueError(name+': boolean is not numeric')
    try:
        n=Decimal(str(value))
    except InvalidOperation:
        raise ValueError(name+': invalid number') from None
    if not n.is_finite() or n<0 or (positive and n==0):
        raise ValueError(name+': invalid range')
    if n.adjusted()>12 or n.as_tuple().exponent < -12:
        raise ValueError(name+': unsupported precision/magnitude')
    if maximum is not None and (n>maximum or (exclusive and n==maximum)):
        raise ValueError(name+': invalid range')
    return n

def canonical(value):
    if not isinstance(value,str): raise ValueError('unit must be text')
    value=value.strip()
    return ALIASES.get(value,value.lower())

def unit(value, conversions=None):
    if value is None: return None
    value=canonical(value)
    if conversions and value in conversions: return conversions[value]
    if value not in UNITS: raise ValueError('unsupported unit: '+str(value))
    return UNITS[value]

def money(n):
    return str(n.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def calculate(data):
    if not isinstance(data,dict): raise ValueError('root must be object')
    for k in ('currency','basis'):
        if not isinstance(data.get(k),str) or not data[k].strip(): raise ValueError(k+' required')
    if 'meals' in data:
        if 'drinks' in data: raise ValueError('use meals or drinks, not both; combine items in one array for shared allocation')
        data={**data,'drinks':data['meals']}
    ingredients={}
    for key in ('ingredients','drinks'):
        if not isinstance(data.get(key),list): raise ValueError(key+' must be array')
    for item in data['ingredients']:
        ident=item['id']
        if not isinstance(ident,str) or not ident or ident in ingredients: raise ValueError('invalid/duplicate ingredient id')
        c=number(item.get('pack_cost'),'pack_cost')
        q=number(item.get('pack_qty'),'pack_qty',positive=True)
        y=number(item.get('yield_rate'),'yield_rate',maximum=1,positive=True)
        conversions={}
        raw=item.get('unit_conversions',{})
        if not isinstance(raw,dict): raise ValueError('unit_conversions must be object')
        for source,spec in raw.items():
            source=canonical(source)
            if source not in UNITS or UNITS[source][0] in ('volume','mass'):
                raise ValueError('only count/packaging units accept explicit conversions')
            if source in conversions: raise ValueError('duplicate unit conversion')
            target=unit(spec.get('unit')); amount=number(spec.get('qty'),'conversion qty',positive=True)
            if target is None or target[0] not in ('volume','mass','count','slice','portion','skewer') or amount is None:
                raise ValueError('conversion requires qty and base unit')
            conversions[source]=(target[0],amount*target[1])
        u=unit(item.get('unit'),conversions)
        ingredients[ident]=(None if any(v is None for v in (c,q,y,u)) else c/(q*u[1]*y),u,conversions)
    results=[]; seen=set(); exact_contributions={}
    for d in data['drinks']:
        ident=d['id']
        if not isinstance(ident,str) or not ident or ident in seen: raise ValueError('invalid/duplicate drink id')
        seen.add(ident)
        missing=[]; subtotal=Decimal(0)
        if not isinstance(d.get('name'),str) or not d['name'].strip(): missing.append('name')
        recipe=d.get('recipe')
        if not isinstance(recipe,list) or not recipe: missing.append('recipe'); recipe=[]
        for index,r in enumerate(recipe):
            prefix='recipe['+str(index)+']'
            q=number(r.get('qty'),prefix+'.qty',positive=True)
            ingredient=ingredients.get(r.get('ingredient_id'))
            u=unit(r.get('unit'),ingredient[2] if ingredient else None)
            if ingredient and ingredient[1] and u and ingredient[1][0]!=u[0]:
                raise ValueError(prefix+': incompatible unit dimensions')
            if q is None or u is None or ingredient is None or ingredient[0] is None:
                missing.append(prefix+': qty/unit/ingredient cost'); continue
            subtotal+=q*u[1]*ingredient[0]
        vals={}
        for k in ('production_loss','packaging_cost','price','discount_rate','fee_rate','fixed_fee'):
            vals[k]=number(d.get(k),k,maximum=1 if k.endswith('rate') or k=='production_loss' else None,exclusive=k=='production_loss')
            if vals[k] is None: missing.append(k)
        qty=number(d.get('quantity'),'quantity')
        if qty is not None and qty!=qty.to_integral_value(): raise ValueError('quantity must be integer')
        out={'id':ident,'name':d.get('name'),'status':'blocked' if missing else 'complete','missing':missing,'known_cost_lower_bound':money(subtotal+(vals['packaging_cost'] or Decimal(0)))}
        if not missing:
            recipe_cost=subtotal/(1-vals['production_loss'])
            cost=recipe_cost+vals['packaging_cost']; revenue=vals['price']*(1-vals['discount_rate'])
            gross=revenue-cost; fees=revenue*vals['fee_rate']+vals['fixed_fee']; contribution=gross-fees
            out.update({k:money(v) for k,v in {'recipe_cost':recipe_cost,'direct_cost':cost,'revenue':revenue,'direct_gross_margin':gross,'channel_fees':fees,'contribution':contribution}.items()})
            out['direct_cost_rate']=str(cost/revenue) if revenue else None
            out['direct_gross_margin_rate']=str(gross/revenue) if revenue else None
            out['period_contribution']=money(contribution*qty) if qty is not None else None
            out['quantity']=int(qty) if qty is not None else None
            exact_contributions[ident]=contribution
        results.append(out)
    overhead=data.get('operating_costs')
    allocation=None
    if overhead is not None:
        if not isinstance(overhead,dict): raise ValueError('operating_costs must be object')
        missing=[]; costs={}; payroll=None
        if 'employees' in overhead:
            if overhead.get('salary') is not None: raise ValueError('use employees or salary, not both')
            employees=overhead['employees']
            if not isinstance(employees,list): raise ValueError('employees must be array')
            payroll=[]; payroll_total=Decimal(0); employee_ids=set()
            if overhead.get('employees_complete') is not True: missing.append('employees_complete confirmation')
            for index,employee in enumerate(employees):
                if not isinstance(employee,dict): raise ValueError('employee must be object')
                ident=employee.get('id')
                if not isinstance(ident,str) or not ident.strip() or ident in employee_ids:
                    raise ValueError('invalid/duplicate employee id')
                employee_ids.add(ident); gaps=[]
                kind=employee.get('pay_type'); base=None
                if kind=='monthly':
                    base=number(employee.get('period_salary'),'period_salary')
                    if base is None: gaps.append('period_salary')
                elif kind=='hourly':
                    rate=number(employee.get('hourly_rate'),'hourly_rate')
                    hours=number(employee.get('hours'),'hours')
                    if rate is None: gaps.append('hourly_rate')
                    if hours is None: gaps.append('hours')
                    if not gaps: base=rate*hours
                else: raise ValueError('pay_type must be monthly or hourly')
                detailed_extra=any(k in employee for k in ('performance_bonus','overtime_pay'))
                extra_details={}
                if detailed_extra:
                    if employee.get('additional_pay') is not None:
                        raise ValueError('use detailed extra pay or additional_pay, not both')
                    for key in ('performance_bonus','overtime_pay'):
                        extra_details[key]=number(employee.get(key),key)
                        if extra_details[key] is None: gaps.append(key)
                    extra=None if any(v is None for v in extra_details.values()) else sum(extra_details.values(),Decimal(0))
                else:
                    extra=number(employee.get('additional_pay'),'additional_pay')
                    if extra is None: gaps.append('additional_pay')
                if gaps: missing.extend('employees['+str(index)+'].'+g for g in gaps)
                amount=None if gaps else base+extra
                if amount is not None: payroll_total+=amount
                payroll.append({'extra_pay_breakdown':{k:money(v) if v is not None else None for k,v in extra_details.items()},'additional_pay_total':money(extra) if extra is not None else None,'sequence':index+1,'id':ident,'pay_type':kind,'status':'blocked' if gaps else 'complete','missing':gaps,'period_pay':money(amount) if amount is not None else None})
            payroll_missing=any(k.startswith('employees') for k in missing)
            costs['salary']=None if payroll_missing else payroll_total
        for key in ('rent','electricity','water','consumables','salary'):
            if key!='salary' or payroll is None:
                costs[key]=number(overhead.get(key),'operating_costs.'+key)
            if costs[key] is None: missing.append(key)
        cups=number(overhead.get('total_cups'),'total_cups',positive=True)
        if cups is not None and cups!=cups.to_integral_value(): raise ValueError('total_cups must be integer')
        if cups is None: missing.append('total_cups')
        if not isinstance(data.get('period'),str) or not data['period'].strip(): missing.append('period')
        if overhead.get('period')!=data.get('period'): missing.append('matching operating_costs.period')
        if overhead.get('consumables_exclude_recipe_and_packaging') is not True:
            missing.append('consumables_exclude_recipe_and_packaging confirmation')
        allocation={'status':'blocked' if missing else 'complete','missing':missing,'method':'equal_per_cup'}
        if payroll is not None:
            allocation['payroll']=payroll
            allocation['salary_total']=money(costs['salary']) if costs['salary'] is not None else None
        if not missing:
            known_sales=sum((number(d.get('quantity'),'quantity') or Decimal(0)) for d in data['drinks'])
            if known_sales>cups: raise ValueError('listed sales exceed total_cups; check period and duplicated channels')
            total=sum(costs.values(),Decimal(0)); per_cup=total/cups
            allocation.update(total_cost=money(total),total_cups=int(cups),cost_per_cup=money(per_cup))
            for result in results:
                if result['status']!='complete': continue
                remaining=exact_contributions[result['id']]-per_cup
                result['allocated_operating_cost_per_cup']=money(per_cup)
                result['contribution_after_listed_operating_costs']=money(remaining)
                result['period_contribution_after_listed_operating_costs']=money(remaining*result['quantity']) if result['quantity'] is not None else None
    output={'currency':data['currency'],'basis':data['basis'],'period':data.get('period'),'results':results}
    if allocation is not None: output['operating_cost_allocation']=allocation
    return output

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('input'); parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        source=Path(args.input); target=Path(args.output)
        if source.resolve()==target.resolve() or (target.exists() and os.path.samefile(source,target)):
            raise ValueError('input and output must differ')
        if source.stat().st_size>2_000_000: raise ValueError('input exceeds 2 MB')
        result=calculate(json.loads(source.read_text(encoding='utf-8-sig')))
        temp_name=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,delete=False) as temp:
                temp_name=temp.name; temp.write(json.dumps(result,ensure_ascii=False,indent=2))
            os.replace(temp_name,target)
        finally:
            if temp_name and Path(temp_name).exists(): Path(temp_name).unlink()
    except (ValueError,KeyError,TypeError,AttributeError,OSError,ArithmeticError) as error:
        print(json.dumps({'status':'validation_error','error':str(error)},ensure_ascii=False),file=sys.stderr); return 2
    return 0
if __name__=='__main__': sys.exit(main())
