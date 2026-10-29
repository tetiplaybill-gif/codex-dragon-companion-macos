"""Build offline reference counts from public Gutenberg English editions.

Developer-only: requires tiktoken; neither tokenizer nor book texts ship in app.
"""
from pathlib import Path
import concurrent.futures,hashlib,json,re,urllib.request,time
import tiktoken
ROOT=Path(__file__).resolve().parent.parent
BOOKS=[(84,'弗兰肯斯坦'),(1342,'傲慢与偏见'),(11,'爱丽丝梦游仙境'),
       (1661,'福尔摩斯冒险史'),(98,'双城记'),(2701,'白鲸'),(345,'德古拉'),
       (1260,'简·爱'),(768,'呼啸山庄'),(174,'道林·格雷的画像'),(120,'金银岛'),
       (1400,'远大前程'),(46,'圣诞颂歌'),(74,'汤姆·索亚历险记'),
       (76,'哈克贝利·费恩历险记'),(16,'彼得·潘'),(55,'绿野仙踪'),
       (35,'时间机器'),(36,'世界大战'),(164,'海底两万里'),(103,'八十天环游地球'),
       (521,'鲁滨逊漂流记'),(1184,'基督山伯爵'),(2600,'战争与和平'),
       (135,'悲惨世界'),(43,'化身博士'),(2814,'都柏林人')]

def build():
    cache=ROOT/'build/book-reference-cache';cache.mkdir(parents=True,exist_ok=True)
    encoder=tiktoken.get_encoding('o200k_base')
    def get(item):
        ident,title=item;url=f'https://www.gutenberg.org/ebooks/{ident}.txt.utf-8';file=cache/f'{ident}.txt'
        if not file.exists():
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BailongBookReference/1.0'}),timeout=45) as response:data=response.read()
                    file.write_bytes(data);break
                except Exception:
                    if attempt==2:raise
                    time.sleep(2)
        raw=file.read_bytes();text=raw.decode('utf-8-sig').replace('\r\n','\n')
        start=re.search(r'^\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\*\*\*',text,re.M)
        end=re.search(r'^\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\*\*\*',text,re.M)
        assert start and end and end.start()>start.end(),f'Missing boundaries: {ident}'
        header=text[:start.start()];body=text[start.end():end.start()].strip()
        def meta(name):
            m=re.search(r'^'+name+r':\s*(.+?)(?=\n\n|\n[A-Z][A-Za-z ]+:)',header,re.M|re.S)
            return ' '.join(m.group(1).split()) if m else ''
        assert meta('Language')=='English',(ident,meta('Language'))
        count=len(encoder.encode_ordinary(body));assert count>15000
        record=dict(id=ident,title=title,originalTitle=meta('Title'),author=meta('Author'),language='English',
                    source=f'https://www.gutenberg.org/ebooks/{ident}',textSource=url,tokens=count,
                    bodySha256=hashlib.sha256(body.encode()).hexdigest(),sourceSha256=hashlib.sha256(raw).hexdigest(),characters=len(body))
        print(json.dumps({k:record[k] for k in ('id','title','originalTitle','tokens')},ensure_ascii=False),flush=True)
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:books=list(pool.map(get,BOOKS))
    catalog=dict(schema=1,tokenizer='o200k_base',tiktokenVersion=tiktoken.__version__,
                 method='Gutenberg English editions; UTF-8, CRLF normalized to LF; text strictly between START/END markers, stripped. Includes edition front matter/notes; excludes Gutenberg license. Reference estimates, not billing counts or Chinese translations.',books=books)
    (ROOT/'app/book_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':build()
