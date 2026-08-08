"""Bounded demo time and reference types shared by runtime and scripted client."""
import re

def validate_constraint(value):
    if not isinstance(value, dict): raise ValueError('invalid time constraint')
    kind = value.get('kind')
    expected = {'kind'} if kind == 'afternoon' else {'kind','time','inclusive'} if kind == 'lower_bound' else {'kind','time'} if kind == 'exact' else set()
    if set(value) != expected or not expected: raise ValueError('invalid time constraint fields')
    if kind != 'afternoon':
        if not re.fullmatch(r'(?:1[2-7]):[0-5][0-9]', str(value['time'])): raise ValueError('outside afternoon')
        if kind == 'lower_bound' and type(value['inclusive']) is not bool: raise ValueError('invalid inclusive')
    return dict(value)

def matches_time(value, time):
    return value['kind'] == 'afternoon' or (time == value['time'] if value['kind'] == 'exact' else time >= value['time'] if value['inclusive'] else time > value['time'])

def parse_time_constraint(content):
    text = content.casefold().replace(' ', '')
    found = re.search(r'(?<!\d)(1[2-7]):([0-5]\d)', text)
    time = found.group(0) if found else '15:30' if any(x in text for x in ('三點半','三点半','3點半','3点半')) else '15:00' if any(x in text for x in ('三點','三点','3pm','3點','3点','after3')) else '14:00' if any(x in text for x in ('兩點','两点','2pm')) else None
    lower = bool(re.search(r'\bafter\b|after(?=\d)|之後|之后|以後|以后|點後|点后|不早於|不早于|或之後|或之后|atleast|>=|唔早過|唔好.*前|先得', content.casefold().replace(' ','')))
    inclusive = any(x in text for x in ('不早於','不早于','或之後','或之后','atleast','>=','唔早過','包括','inclusive','唔好'))
    if '先得' in text and not any(x in text for x in ('之後','之后','點後','点后','after')): inclusive = True
    if time and lower: return {'kind':'lower_bound','time':time,'inclusive':inclusive}
    if time and any(x in text for x in ('改','change','instead','exact','只要','正好','返去','回到','改為','改为')): return {'kind':'exact','time':time}
    if 'afternoon' in text or '下午' in text: return {'kind':'afternoon'}
    return None

def selection_target(content, presentation=None):
    text = content.casefold()
    match = re.search(r'(?<!\d)(1[2-7]):([0-5]\d)', text)
    if match: return {'kind':'time','time':match.group(0)}
    match = re.search(r'第([一二三四五六七八九]|\d+)個|(?:the\s+)?(first|second|third|fourth)', text)
    if match:
        digits = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'first':1,'second':2,'third':3,'fourth':4}
        token = match.group(1) or match.group(2)
        return {'kind':'ordinal','ordinal':digits.get(token,int(token) if token.isdigit() else 0),'presentation_id':(presentation or {}).get('presentation_id')}
    if any(x in text for x in ('current slot','that slot','this slot','呢個時段','這個時段','这个时段','就呢個')): return {'kind':'current'}
    return None

parse_selection_target = selection_target

def validate_target(value):
    if not isinstance(value, dict):
        raise ValueError('selection target must be an object')
    kind = value.get('kind')
    fields = {'current':{'kind'}, 'time':{'kind','time'}, 'ordinal':{'kind','ordinal','presentation_id'}, 'slot_id':{'kind','slot_id'}}
    if kind not in fields or set(value) != fields[kind]:
        raise ValueError('invalid target fields')
    if kind == 'time' and not re.fullmatch(r'1[2-7]:[0-5][0-9]',str(value['time'])):
        raise ValueError('invalid target time')
    if kind == 'ordinal' and (type(value['ordinal']) is not int or value['ordinal'] < 1 or not isinstance(value['presentation_id'],str) or not value['presentation_id']):
        raise ValueError('ordinal requires positive index and presentation ID')
    if kind == 'slot_id' and (not isinstance(value['slot_id'],str) or not value['slot_id']):
        raise ValueError('slot ID required')
    return dict(value)
