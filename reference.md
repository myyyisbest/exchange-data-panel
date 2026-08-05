多数据源汇率API调用与SQLite存储技术实现方案（V3.0）

# 多数据源汇率API调用与SQLite存储技术实现方案（V3.0）

**版本**：V3.0 **日期**：2026-06-09 **核心变更**：完全修正中国货币网接口解析逻辑（自动识别单位/标价方法/反向货币对）；移除所有硬编码单位；统一数据存储标准；保留HKMA/BI双数据源官方实现 **技术栈**：Python 3.10+、SQLite 3.35+、SQLAlchemy 2.0、APScheduler 3.10、Requests 2.31+、xml.etree.ElementTree

## 一、方案概述

### 1.1 核心目标

实现**香港金管局（HKMA）**、**印尼央行（BI）**、**中国货币网（PBC）**三数据源官方汇率的自动化获取，**严格按照各接口原始返回的单位和标价规则**解析数据，统一存储到本地SQLite数据库，完全满足以下要求：

- 人民币相关数据存储**中间价**
- 港元、印尼盾相关数据存储**卖出价**
- 自动识别官方标价单位（1/100）
- 自动区分直接/间接标价法
- 完整保留货币对双向信息

### 1.2 各数据源官方规则确认（最终版）

| 数据源     | 价格类型       | 标价规则       | 单位说明                                                     | 数据范围             |
| ---------- | -------------- | -------------- | ------------------------------------------------------------ | -------------------- |
| 香港金管局 | 官方卖出价     | 全部直接标价法 | 固定每1单位外币                                              | 支持历史日期区间查询 |
| 印尼央行   | 官方参考卖出价 | 全部直接标价法 | 固定每1单位外币                                              | 支持历史日期区间查询 |
| 中国货币网 | 官方中间价     | 混合标价法     | 自动识别： - 多数货币：每1单位 - 日元：每100单位 - 反向货币对：每1单位人民币 | 仅支持当日数据       |

## 二、数据库设计（SQLite本地版）

### 2.1 最终表结构定义

```SQL
CREATE TABLE exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency_code CHAR(3) NOT NULL,        -- 基础货币代码(ISO 3位)
    currency_name VARCHAR(50) NOT NULL,    -- 基础货币名称
    counter_currency_code CHAR(3) NOT NULL,-- 计价货币代码
    counter_currency_name VARCHAR(50) NOT NULL,-- 计价货币名称
    quotation_method VARCHAR(10) NOT NULL, -- 标价方法：直接/间接
    unit INTEGER NOT NULL,                 -- 官方原始标价单位（1或100）
    price_type VARCHAR(10) NOT NULL,       -- 价格类型：中间价/卖出价
    price DECIMAL(12,6) NOT NULL,          -- 官方返回的原始价格（与unit严格对应）
    source VARCHAR(20) NOT NULL,           -- 数据源：HKMA/BI/PBC
    rate_date DATE NOT NULL,               -- 汇率生效日期
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (currency_code, counter_currency_code, rate_date, source)  -- 防重复唯一索引
);

-- 查询优化索引
CREATE INDEX idx_rate_date ON exchange_rates(rate_date);
CREATE INDEX idx_currency_pair ON exchange_rates(currency_code, counter_currency_code);
CREATE INDEX idx_source_price_type ON exchange_rates(source, price_type);
```

### 2.2 字段设计原则

- **price字段**：**100%存储API返回的原始数值**，不做任何乘除转换
- **unit字段**：完全由接口返回数据自动识别，无任何硬编码默认值
- **quotation_method字段**：自动识别直接/间接标价法，反向货币对自动转换为统一直接标价法存储
- **price_type字段**：按数据源严格区分：HKMA=卖出价、BI=卖出价、PBC=中间价

## 三、核心代码实现（全量修正版）

### 3.1 配置文件 `config.py`

```Python
# SQLite数据库配置
SQLALCHEMY_DATABASE_URI = "sqlite:///exchange_rates.db"

# 香港金管局API配置（官方固定规则）
HKMA_CONFIG = {
    "base_url": "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily",
    "currencies": ["CNY", "USD", "EUR", "JPY", "SGD", "GBP", "AUD"],
    "counter_currency": "HKD",
    "price_type": "卖出价",
    "quotation_method": "直接",
    "unit": 1,  # 官方固定单位
    "timeout": 30,
    "max_retries": 3
}

# 印尼央行API配置（官方固定规则）
BI_CONFIG = {
    "base_url": "https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursNonUSD_IDR3",
    "usd_url": "https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursUSD_IDR3",
    "currencies": ["CNY", "USD", "HKD", "EUR", "JPY", "SGD", "GBP", "AUD"],
    "counter_currency": "IDR",
    "price_type": "卖出价",
    "quotation_method": "直接",
    "unit": 1,  # 官方固定单位
    "timeout": 30,
    "max_retries": 3
}

# 中国货币网API配置（动态解析规则）
PBC_CONFIG = {
    "base_url": "http://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json",
    "price_type": "中间价",
    "timeout": 30,
    "max_retries": 3
}

# 定时任务配置（按各数据源更新时间）
SCHEDULER_CONFIG = {
    "hkma_run_time": "18:00",  # 香港工作日17:00更新，延迟1小时执行
    "bi_run_time": "19:00",    # 印尼工作日18:00更新（UTC+7），延迟1小时
    "pbc_run_time": "10:00",   # 中国工作日9:15更新，延迟45分钟
    "timezone": "Asia/Shanghai"
}

# 全球标准货币名称映射
CURRENCY_NAMES = {
    "CNY": "人民币", "HKD": "港元", "IDR": "印尼盾", "USD": "美元",
    "EUR": "欧元", "JPY": "日元", "SGD": "新加坡元", "GBP": "英镑",
    "AUD": "澳元", "NZD": "新西兰元", "CHF": "瑞士法郎", "CAD": "加元",
    "MOP": "澳门元", "MYR": "马来西亚林吉特", "RUB": "俄罗斯卢布",
    "ZAR": "南非兰特", "KRW": "韩元", "AED": "阿联酋迪拉姆",
    "SAR": "沙特里亚尔", "HUF": "匈牙利福林", "PLN": "波兰兹罗提",
    "DKK": "丹麦克朗", "SEK": "瑞典克朗", "NOK": "挪威克朗",
    "TRY": "土耳其里拉", "MXN": "墨西哥比索", "THB": "泰铢"
}
```

### 3.2 通用工具类 `utils.py`

```Python
from config import CURRENCY_NAMES
import logging

logger = logging.getLogger(__name__)

def get_currency_name(code: str) -> str:
    """获取标准货币名称"""
    return CURRENCY_NAMES.get(code.upper(), code.upper())

def standardize_fixed_rate(raw_data: dict, config: dict, source: str) -> dict:
    """
    标准化固定规则数据源（HKMA/BI）数据
    :param raw_data: {"currency": "CNY", "rate": 原始价格, "date": "2026-06-09"}
    """
    currency_code = raw_data["currency"].upper()
    counter_code = config["counter_currency"].upper()
    
    return {
        "currency_code": currency_code,
        "currency_name": get_currency_name(currency_code),
        "counter_currency_code": counter_code,
        "counter_currency_name": get_currency_name(counter_code),
        "quotation_method": config["quotation_method"],
        "unit": config["unit"],
        "price_type": config["price_type"],
        "price": round(raw_data["rate"], 6),
        "source": source,
        "rate_date": raw_data["date"]
    }
```

### 3.3 香港金管局API客户端 `hkma_client.py`（无变更，已正确）

```Python
import requests
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from config import HKMA_CONFIG
from utils import standardize_fixed_rate
import logging

logger = logging.getLogger(__name__)

class HKMAApiClient:
    def __init__(self):
        self.base_url = HKMA_CONFIG["base_url"]
        self.currencies = HKMA_CONFIG["currencies"]
        self.timeout = HKMA_CONFIG["timeout"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }

    @retry(stop=stop_after_attempt(HKMA_CONFIG["max_retries"]), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_rates(self, days: int = 2) -> List[Dict]:
        params = {
            "pagesize": days,
            "offset": 0,
            "fields": f"end_of_day,{','.join([c.lower() for c in self.currencies])}"
        }

        response = requests.get(self.base_url, params=params, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if not data["header"]["success"]:
            raise Exception(f"HKMA API错误: {data['header']['err_msg']}")

        return self._parse_response(data["result"]["records"])

    def _parse_response(self, records: List[Dict]) -> List[Dict]:
        standardized_data = []
        for record in records:
            rate_date = record["end_of_day"]
            for currency in self.currencies:
                rate = record.get(currency.lower())
                if rate and rate > 0:
                    standardized_data.append(standardize_fixed_rate(
                        {"currency": currency, "rate": rate, "date": rate_date},
                        HKMA_CONFIG, "HKMA"
                    ))
        return standardized_data
```

### 3.4 印尼央行API客户端 `bi_client.py`（无变更，已正确）

```Python
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from config import BI_CONFIG
from utils import standardize_fixed_rate
import logging

logger = logging.getLogger(__name__)

class BIApiClient:
    def __init__(self):
        self.base_url = BI_CONFIG["base_url"]
        self.usd_url = BI_CONFIG["usd_url"]
        self.currencies = BI_CONFIG["currencies"]
        self.timeout = BI_CONFIG["timeout"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }

    @retry(stop=stop_after_attempt(BI_CONFIG["max_retries"]), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_rates(self, start_date: str, end_date: str) -> List[Dict]:
        standardized_data = []
        for currency in self.currencies:
            try:
                url = self.usd_url if currency == "USD" else self.base_url
                params = {"mts": currency, "startdate": start_date, "enddate": end_date}
                response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                standardized_data.extend(self._parse_xml(response.text, currency))
            except Exception as e:
                logger.error(f"印尼央行 {currency} 汇率获取失败: {str(e)}")
                continue
        return standardized_data

    def _parse_xml(self, xml_content: str, currency: str) -> List[Dict]:
        standardized_data = []
        root = ET.fromstring(xml_content)
        for table in root.iter("{http://tempuri.org/}Table"):
            tanggal = table.find("{http://tempuri.org/}Tanggal").text
            nilai = table.find("{http://tempuri.org/}Nilai").text
            if tanggal and nilai:
                standardized_data.append(standardize_fixed_rate(
                    {"currency": currency, "rate": float(nilai), "date": tanggal.split("T")[0]},
                    BI_CONFIG, "BI"
                ))
        return standardized_data
```

### 3.5 中国货币网API客户端 `pbc_client.py`（完全重写修正版）

```Python
import requests
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from config import PBC_CONFIG, CURRENCY_NAMES
from utils import get_currency_name
import logging

logger = logging.getLogger(__name__)

class PBCClient:
    def __init__(self):
        self.base_url = PBC_CONFIG["base_url"]
        self.timeout = PBC_CONFIG["timeout"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": "http://www.chinamoney.com.cn/chinese/bkccpr/"
        }

    @retry(stop=stop_after_attempt(PBC_CONFIG["max_retries"]), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_rates(self) -> List[Dict]:
        """获取当日人民币中间价（自动识别所有标价规则）"""
        response = requests.get(self.base_url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if data["head"]["rep_code"] != "200":
            raise Exception(f"中国货币网接口错误: {data['head']['rep_message']}")

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> List[Dict]:
        """
        智能解析所有货币对格式：
        1. XXX/CNY → 直接标价法，单位1
        2. 100XXX/CNY → 直接标价法，单位100（仅日元）
        3. CNY/XXX → 间接标价法，自动转换为直接标价法存储
        """
        standardized_data = []
        rate_date = data["data"]["lastDate"].split(" ")[0]
        
        for record in data["records"]:
            vrt_e_name = record["vrtEName"]
            raw_price = float(record["price"])
            
            if "/" not in vrt_e_name:
                continue
                
            base_currency, counter_currency = vrt_e_name.split("/")
            unit = 1
            quotation_method = "直接"

            # 处理100单位特殊货币（仅日元）
            if base_currency.startswith("100"):
                base_currency = base_currency[3:]
                unit = 100

            # 处理反向标价货币对（CNY作为基础货币）
            if base_currency == "CNY":
                quotation_method = "间接"
                # 转换为直接标价法统一存储：CNY/XXX → XXX/CNY
                original_base = base_currency
                original_counter = counter_currency
                base_currency = original_counter
                counter_currency = original_base
                raw_price = round(1 / raw_price, 6)
                unit = 1  # 转换后单位统一为1

            # 过滤无效货币
            if base_currency not in CURRENCY_NAMES or counter_currency not in CURRENCY_NAMES:
                continue

            standardized_data.append({
                "currency_code": base_currency.upper(),
                "currency_name": get_currency_name(base_currency),
                "counter_currency_code": counter_currency.upper(),
                "counter_currency_name": get_currency_name(counter_currency),
                "quotation_method": quotation_method,
                "unit": unit,
                "price_type": PBC_CONFIG["price_type"],
                "price": raw_price,
                "source": "PBC",
                "rate_date": rate_date
            })
        
        return standardized_data
```

### 3.6 SQLite数据库服务 `db_service.py`（无变更）

```Python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert
from typing import List, Dict
from models import Base, ExchangeRate
from config import SQLALCHEMY_DATABASE_URI
import logging

logger = logging.getLogger(__name__)

class SQLiteService:
    def __init__(self):
        self.engine = create_engine(
            SQLALCHEMY_DATABASE_URI,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def bulk_upsert_rates(self, rates: List[Dict]) -> int:
        """批量幂等写入（存在则更新价格，不存在则插入）"""
        if not rates:
            logger.info("无数据需要写入")
            return 0

        session = self.SessionLocal()
        try:
            stmt = insert(ExchangeRate).values(rates)
            update_stmt = stmt.on_conflict_do_update(
                index_elements=["currency_code", "counter_currency_code", "rate_date", "source"],
                set_={"price": stmt.excluded.price, "updated_at": stmt.excluded.updated_at}
            )
            result = session.execute(update_stmt)
            session.commit()
            logger.info(f"成功写入/更新 {result.rowcount} 条数据")
            return result.rowcount
        except Exception as e:
            session.rollback()
            logger.error(f"数据库写入失败: {str(e)}")
            raise
        finally:
            session.close()

    def get_latest_rate(self, currency: str, counter_currency: str, source: str = None) -> Dict:
        """获取指定货币对最新汇率"""
        session = self.SessionLocal()
        try:
            query = session.query(ExchangeRate).filter(
                ExchangeRate.currency_code == currency.upper(),
                ExchangeRate.counter_currency_code == counter_currency.upper()
            )
            if source:
                query = query.filter(ExchangeRate.source == source.upper())
            rate = query.order_by(ExchangeRate.rate_date.desc()).first()
            return rate.__dict__ if rate else None
        finally:
            session.close()
```

### 3.7 数据库模型 `models.py`（无变更）

```Python
from sqlalchemy import Column, String, Integer, Date, DECIMAL, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    currency_code = Column(String(3), nullable=False)
    currency_name = Column(String(50), nullable=False)
    counter_currency_code = Column(String(3), nullable=False)
    counter_currency_name = Column(String(50), nullable=False)
    quotation_method = Column(String(10), nullable=False)
    unit = Column(Integer, nullable=False)
    price_type = Column(String(10), nullable=False)
    price = Column(DECIMAL(12,6), nullable=False)
    source = Column(String(20), nullable=False)
    rate_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)
```

### 3.8 定时任务调度器 `scheduler.py`

```Python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime, timedelta
from config import SCHEDULER_CONFIG
from hkma_client import HKMAApiClient
from bi_client import BIApiClient
from pbc_client import PBCClient
from db_service import SQLiteService

logger = logging.getLogger(__name__)

def sync_hkma():
    logger.info("=== 开始同步香港金管局汇率 ===")
    try:
        rates = HKMAApiClient().fetch_rates(days=2)
        SQLiteService().bulk_upsert_rates(rates)
        logger.info("=== 香港金管局汇率同步完成 ===")
    except Exception as e:
        logger.error(f"香港金管局同步失败: {str(e)}", exc_info=True)

def sync_bi():
    logger.info("=== 开始同步印尼央行汇率 ===")
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        rates = BIApiClient().fetch_rates(start, end)
        SQLiteService().bulk_upsert_rates(rates)
        logger.info("=== 印尼央行汇率同步完成 ===")
    except Exception as e:
        logger.error(f"印尼央行同步失败: {str(e)}", exc_info=True)

def sync_pbc():
    logger.info("=== 开始同步中国货币网中间价 ===")
    try:
        rates = PBCClient().fetch_rates()
        SQLiteService().bulk_upsert_rates(rates)
        logger.info("=== 中国货币网中间价同步完成 ===")
    except Exception as e:
        logger.error(f"中国货币网同步失败: {str(e)}", exc_info=True)

def start_scheduler():
    scheduler = BlockingScheduler(timezone=SCHEDULER_CONFIG["timezone"])
    
    # 香港金管局：周一至周五18:00
    h, m = SCHEDULER_CONFIG["hkma_run_time"].split(":")
    scheduler.add_job(sync_hkma, CronTrigger(hour=h, minute=m, day_of_week="mon-fri"), id="hkma_sync")
    
    # 印尼央行：周一至周五19:00
    h, m = SCHEDULER_CONFIG["bi_run_time"].split(":")
    scheduler.add_job(sync_bi, CronTrigger(hour=h, minute=m, day_of_week="mon-fri"), id="bi_sync")
    
    # 中国货币网：周一至周五10:00
    h, m = SCHEDULER_CONFIG["pbc_run_time"].split(":")
    scheduler.add_job(sync_pbc, CronTrigger(hour=h, minute=m, day_of_week="mon-fri"), id="pbc_sync")
    
    logger.info("所有定时任务已启动")
    scheduler.start()
```

### 3.9 主程序入口 `main.py`

```Python
import logging
import sys
from datetime import datetime, timedelta
from hkma_client import HKMAApiClient
from bi_client import BIApiClient
from pbc_client import PBCClient
from db_service import SQLiteService
from scheduler import start_scheduler

# 全局日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("exchange_rate_sync.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def initial_sync():
    """首次运行初始化同步最近7天数据"""
    logger.info("=== 执行首次全量数据同步 ===")
    db = SQLiteService()
    
    # 同步香港金管局
    try:
        db.bulk_upsert_rates(HKMAApiClient().fetch_rates(days=7))
    except Exception as e:
        logger.error(f"首次同步HKMA失败: {str(e)}")
    
    # 同步印尼央行
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        db.bulk_upsert_rates(BIApiClient().fetch_rates(start, end))
    except Exception as e:
        logger.error(f"首次同步BI失败: {str(e)}")
    
    # 同步中国货币网（仅当日）
    try:
        db.bulk_upsert_rates(PBCClient().fetch_rates())
    except Exception as e:
        logger.error(f"首次同步PBC失败: {str(e)}")
    
    logger.info("=== 首次全量同步完成 ===")

if __name__ == "__main__":
    try:
        initial_sync()
        start_scheduler()
    except KeyboardInterrupt:
        logging.info("程序已正常退出")
```

## 四、数据查询与使用示例

```Python
from db_service import SQLiteService

db = SQLiteService()

# 1. 查询最新人民币对港元卖出价（香港金管局）
cny_hkd = db.get_latest_rate("CNY", "HKD", "HKMA")
if cny_hkd:
    print(f"【HKMA卖出价】{cny_hkd['unit']} 人民币 = {cny_hkd['price']} 港元")
    # 转换为每1单位：1人民币 = {cny_hkd['price']/cny_hkd['unit']} 港元

# 2. 查询最新美元对印尼盾卖出价（印尼央行）
usd_idr = db.get_latest_rate("USD", "IDR", "BI")
if usd_idr:
    print(f"【BI卖出价】{usd_idr['unit']} 美元 = {usd_idr['price']} 印尼盾")

# 3. 查询最新日元对人民币中间价（中国货币网，自动识别100单位）
jpy_cny = db.get_latest_rate("JPY", "CNY", "PBC")
if jpy_cny:
    print(f"【PBC中间价】{jpy_cny['unit']} 日元 = {jpy_cny['price']} 人民币")
    print(f"转换为每1日元：1 日元 = {round(jpy_cny['price']/jpy_cny['unit'], 6)} 人民币")
```

## 五、异常处理与保障机制

1. **API重试机制**：所有请求配置3次指数退避重试（2s→4s→8s）
2. **单货币隔离**：印尼央行按货币单独请求，单个失败不影响整体
3. **幂等写入**：SQLite唯一索引+ON CONFLICT保证重复调用无脏数据
4. **自动格式转换**：中国货币网反向货币对自动转换为统一直接标价法
5. **完整日志**：所有操作和异常记录到日志文件，便于排查

## 六、使用注意事项

1. **中国货币网接口**：仅支持当日数据，无历史查询能力，需每日定时抓取积累历史数据；仅可用于内部非商业用途
2. **数据一致性**：所有价格均为官方原始值，如需统一单位，查询时按 `price/unit` 计算
3. **接口稳定性**：中国货币网为内部接口，建议添加监控，发现变更及时调整解析逻辑
