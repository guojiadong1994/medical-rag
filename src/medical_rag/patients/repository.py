from copy import deepcopy


_PATIENTS: list[dict] = [
    {
        "id": "P10001",
        "patientNo": "JD-2026-000128",
        "name": "张某",
        "gender": "男",
        "age": 67,
        "diagnoses": ["高血压", "2型糖尿病", "高脂血症"],
        "lastVisit": "2026-08-08",
        "riskLevel": "高",
        "status": "需关注",
        "phoneMasked": "138****2186",
        "allergies": ["青霉素"],
        "chronicDiseases": ["高血压（10年）", "2型糖尿病（5年）", "高脂血症"],
        "careSummary": "近三年血压控制仍不稳定，糖化血红蛋白呈缓慢升高趋势，同时存在血脂异常，需要持续关注血压、血糖与心血管综合风险。",
        "recentMetrics": [
            {"name": "血压", "value": "155/96", "unit": "mmHg", "date": "2026-08-08", "status": "偏高"},
            {"name": "糖化血红蛋白", "value": "8.1", "unit": "%", "date": "2026-08-08", "status": "偏高"},
            {"name": "低密度脂蛋白胆固醇", "value": "4.1", "unit": "mmol/L", "date": "2026-08-08", "status": "偏高"},
            {"name": "肌酐", "value": "92", "unit": "μmol/L", "date": "2026-08-08", "status": "正常"},
        ],
        "currentMedications": [
            {"name": "硝苯地平控释片", "dose": "30 mg", "frequency": "每日一次", "startDate": "2024-05-12", "status": "当前"},
            {"name": "二甲双胍片", "dose": "0.5 g", "frequency": "每日两次", "startDate": "2024-02-18", "status": "当前"},
            {"name": "阿托伐他汀钙片", "dose": "20 mg", "frequency": "每晚一次", "startDate": "2025-03-06", "status": "当前"},
        ],
        "timeline": [
            {"id": "E1001", "date": "2026-08-08", "type": "门诊", "title": "慢病随访门诊", "summary": "血压 155/96 mmHg，糖化血红蛋白 8.1%，继续慢病综合评估。", "source": "门诊记录"},
            {"id": "E1002", "date": "2026-08-08", "type": "检验", "title": "血糖与血脂复查", "summary": "HbA1c 8.1%，LDL-C 4.1 mmol/L，较上次升高。", "source": "检验系统"},
            {"id": "E1003", "date": "2026-03-11", "type": "检查", "title": "眼底检查", "summary": "未见急性视网膜病变表现，建议按期复查。", "source": "检查报告"},
            {"id": "E1004", "date": "2025-08-21", "type": "门诊", "title": "糖尿病随访", "summary": "HbA1c 7.8%，血压 148/91 mmHg。", "source": "门诊记录"},
            {"id": "E1005", "date": "2024-05-10", "type": "门诊", "title": "高血压随访", "summary": "血压 150/93 mmHg，调整长期监测计划。", "source": "门诊记录"},
        ],
    },
    {
        "id": "P10002", "patientNo": "JD-2026-000214", "name": "李某", "gender": "女", "age": 58,
        "diagnoses": ["高脂血症", "冠心病"], "lastVisit": "2026-08-06", "riskLevel": "中", "status": "随访中",
        "phoneMasked": "136****6731", "allergies": [], "chronicDiseases": ["冠心病（3年）", "高脂血症"],
        "careSummary": "近期生命体征平稳，继续关注血脂控制、运动耐量和心血管相关症状变化。",
        "recentMetrics": [
            {"name": "血压", "value": "132/82", "unit": "mmHg", "date": "2026-08-06", "status": "正常"},
            {"name": "低密度脂蛋白胆固醇", "value": "3.2", "unit": "mmol/L", "date": "2026-08-06", "status": "偏高"},
        ],
        "currentMedications": [
            {"name": "阿托伐他汀钙片", "dose": "20 mg", "frequency": "每晚一次", "startDate": "2025-01-16", "status": "当前"},
            {"name": "阿司匹林肠溶片", "dose": "100 mg", "frequency": "每日一次", "startDate": "2025-01-16", "status": "当前"},
        ],
        "timeline": [
            {"id": "E2001", "date": "2026-08-06", "type": "门诊", "title": "心血管随访", "summary": "近期无明显胸痛，继续观察运动耐量与血脂变化。", "source": "门诊记录"},
            {"id": "E2002", "date": "2026-08-06", "type": "检验", "title": "血脂复查", "summary": "LDL-C 3.2 mmol/L。", "source": "检验系统"},
        ],
    },
    {
        "id": "P10003", "patientNo": "JD-2026-000307", "name": "赵某", "gender": "男", "age": 72,
        "diagnoses": ["高血压", "慢性肾病"], "lastVisit": "2026-08-05", "riskLevel": "高", "status": "需关注",
        "phoneMasked": "139****1088", "allergies": [], "chronicDiseases": ["高血压（15年）", "慢性肾病"],
        "careSummary": "血压与肾功能需要联合长期观察，近期肾功能指标存在异常，需持续关注指标变化和用药安全。",
        "recentMetrics": [
            {"name": "血压", "value": "158/94", "unit": "mmHg", "date": "2026-08-05", "status": "偏高"},
            {"name": "肌酐", "value": "146", "unit": "μmol/L", "date": "2026-08-05", "status": "偏高"},
        ],
        "currentMedications": [
            {"name": "氨氯地平片", "dose": "5 mg", "frequency": "每日一次", "startDate": "2023-06-11", "status": "当前"},
        ],
        "timeline": [
            {"id": "E3001", "date": "2026-08-05", "type": "门诊", "title": "肾内科随访", "summary": "血压偏高，结合肾功能指标继续评估。", "source": "门诊记录"},
            {"id": "E3002", "date": "2026-08-05", "type": "检验", "title": "肾功能检查", "summary": "肌酐 146 μmol/L。", "source": "检验系统"},
        ],
    },
    {
        "id": "P10004", "patientNo": "JD-2026-000419", "name": "周某", "gender": "女", "age": 49,
        "diagnoses": ["甲状腺结节"], "lastVisit": "2026-08-03", "riskLevel": "低", "status": "稳定",
        "phoneMasked": "135****5260", "allergies": [], "chronicDiseases": ["甲状腺结节"],
        "careSummary": "近期甲状腺相关指标稳定，按既定随访计划复查即可。",
        "recentMetrics": [{"name": "促甲状腺激素", "value": "2.1", "unit": "mIU/L", "date": "2026-08-03", "status": "正常"}],
        "currentMedications": [],
        "timeline": [{"id": "E4001", "date": "2026-08-03", "type": "检查", "title": "甲状腺超声复查", "summary": "结节较前无明显变化。", "source": "检查报告"}],
    },
    {
        "id": "P10005", "patientNo": "JD-2026-000523", "name": "陈某", "gender": "男", "age": 63,
        "diagnoses": ["2型糖尿病"], "lastVisit": "2026-07-30", "riskLevel": "中", "status": "随访中",
        "phoneMasked": "137****3019", "allergies": [], "chronicDiseases": ["2型糖尿病（7年）"],
        "careSummary": "血糖控制基本稳定，继续关注糖化血红蛋白、肾功能及糖尿病相关并发症筛查。",
        "recentMetrics": [{"name": "糖化血红蛋白", "value": "7.2", "unit": "%", "date": "2026-07-30", "status": "偏高"}],
        "currentMedications": [{"name": "二甲双胍片", "dose": "0.5 g", "frequency": "每日两次", "startDate": "2022-04-09", "status": "当前"}],
        "timeline": [{"id": "E5001", "date": "2026-07-30", "type": "门诊", "title": "糖尿病随访", "summary": "糖化血红蛋白 7.2%，继续定期随访。", "source": "门诊记录"}],
    },
    {
        "id": "P10006", "patientNo": "JD-2026-000631", "name": "刘某", "gender": "女", "age": 70,
        "diagnoses": ["骨质疏松", "高血压"], "lastVisit": "2026-07-28", "riskLevel": "中", "status": "随访中",
        "phoneMasked": "133****8182", "allergies": [], "chronicDiseases": ["骨质疏松", "高血压"],
        "careSummary": "近期血压总体平稳，结合骨质疏松情况继续关注跌倒风险、骨密度和长期用药情况。",
        "recentMetrics": [{"name": "血压", "value": "138/86", "unit": "mmHg", "date": "2026-07-28", "status": "正常"}],
        "currentMedications": [{"name": "碳酸钙D3片", "dose": "1片", "frequency": "每日一次", "startDate": "2025-06-02", "status": "当前"}],
        "timeline": [{"id": "E6001", "date": "2026-07-28", "type": "门诊", "title": "综合慢病随访", "summary": "血压基本稳定，继续骨质疏松健康管理。", "source": "门诊记录"}],
    },
    {
        "id": "P10007", "patientNo": "JD-2026-000744", "name": "吴某", "gender": "男", "age": 54,
        "diagnoses": ["脂肪肝", "高尿酸血症"], "lastVisit": "2026-07-26", "riskLevel": "低", "status": "稳定",
        "phoneMasked": "188****6593", "allergies": [], "chronicDiseases": ["脂肪肝", "高尿酸血症"],
        "careSummary": "目前总体状态稳定，继续关注体重、尿酸和肝功能变化。",
        "recentMetrics": [{"name": "尿酸", "value": "438", "unit": "μmol/L", "date": "2026-07-26", "status": "偏高"}],
        "currentMedications": [],
        "timeline": [{"id": "E7001", "date": "2026-07-26", "type": "检验", "title": "肝功能与尿酸复查", "summary": "尿酸 438 μmol/L。", "source": "检验系统"}],
    },
    {
        "id": "P10008", "patientNo": "JD-2026-000852", "name": "孙某", "gender": "女", "age": 61,
        "diagnoses": ["高血压"], "lastVisit": "2026-07-22", "riskLevel": "中", "status": "随访中",
        "phoneMasked": "150****1472", "allergies": [], "chronicDiseases": ["高血压（6年）"],
        "careSummary": "近期血压存在波动，继续记录家庭血压并结合门诊结果进行长期评估。",
        "recentMetrics": [{"name": "血压", "value": "146/90", "unit": "mmHg", "date": "2026-07-22", "status": "偏高"}],
        "currentMedications": [{"name": "缬沙坦胶囊", "dose": "80 mg", "frequency": "每日一次", "startDate": "2024-03-20", "status": "当前"}],
        "timeline": [{"id": "E8001", "date": "2026-07-22", "type": "门诊", "title": "高血压随访", "summary": "门诊血压 146/90 mmHg，继续家庭血压监测。", "source": "门诊记录"}],
    },
]


def list_patients() -> list[dict]:
    keys = {"id", "patientNo", "name", "gender", "age", "diagnoses", "lastVisit", "riskLevel", "status"}
    return [{key: patient[key] for key in keys} for patient in deepcopy(_PATIENTS)]


def get_patient(patient_id: str) -> dict | None:
    for patient in _PATIENTS:
        if patient["id"] == patient_id:
            return deepcopy(patient)
    return None
