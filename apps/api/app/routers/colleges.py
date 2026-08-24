import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import verify_maintenance_key
from app.models import University, College, Department, DepartmentCatalog

router = APIRouter(prefix="/colleges", tags=["colleges"])

# ── Schemas ────────────────────────────────────────────────────────


class CollegeOut(BaseModel):
    id: str
    code: str
    name: str
    duration_years: int

    model_config = {"from_attributes": True}


class DepartmentOut(BaseModel):
    id: str
    code: str
    name: str

    model_config = {"from_attributes": True}


class UniversityOut(BaseModel):
    id: str
    code: str
    name: str
    program_type: str = "university"

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=list[UniversityOut])
async def list_universities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(University).order_by(University.name))
    return result.scalars().all()


@router.get("/{university_id}/colleges", response_model=list[CollegeOut])
async def list_colleges(university_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(College).where(College.university_id == university_id).order_by(College.name)
    )
    return result.scalars().all()


@router.get("/colleges/{college_id}/departments", response_model=list[DepartmentOut])
async def list_departments(college_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Department).where(Department.college_id == college_id).order_by(Department.name)
    )
    return result.scalars().all()


# ── Seed data (University → College → Departments) ────────────────

#: Standard college set applied to universities that don't define their own.
DEFAULT_COLLEGES: list[dict] = [
    {
        "code": "SCI",
        "name": "Faculty of Science",
        "duration_years": 4,
        "departments": [
            ("CSC", "Computer Science"),
            ("BCH", "Biochemistry"),
            ("CHM", "Chemistry"),
            ("PHY", "Physics"),
            ("MTH", "Mathematics"),
            ("BIO", "Biology"),
        ],
    },
    {
        "code": "ENG",
        "name": "Faculty of Engineering",
        "duration_years": 5,
        "departments": [
            ("EEE", "Electrical & Electronics Engineering"),
            ("MEE", "Mechanical Engineering"),
            ("CVE", "Civil Engineering"),
        ],
    },
    {
        "code": "ART",
        "name": "Faculty of Arts",
        "duration_years": 4,
        "departments": [
            ("ENG", "English & Literary Studies"),
            ("HIS", "History & International Studies"),
        ],
    },
    {
        "code": "SMS",
        "name": "Faculty of Social & Management Sciences",
        "duration_years": 4,
        "departments": [
            ("ACC", "Accounting"),
            ("BUS", "Business Administration"),
            ("ECO", "Economics"),
            ("MKT", "Mass Communication"),
        ],
    },
    {
        "code": "LAW",
        "name": "Faculty of Law",
        "duration_years": 5,
        "departments": [("LAW", "Law")],
    },
    {
        "code": "MED",
        "name": "Faculty of Medicine",
        "duration_years": 6,
        "departments": [
            ("MBB", "Medicine & Surgery"),
            ("NSC", "Nursing Science"),
        ],
    },
]


def _normalize_name(name: str) -> str:
    import re

    return re.sub(r"\s+", " ", name.strip().lower())


SEED_DATA: list[dict] = [
    {
        "code": "UNILAG",
        "name": "University of Lagos",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                    ("CHM", "Chemistry"),
                    ("PHY", "Physics"),
                    ("MTH", "Mathematics"),
                    ("BIO", "Biology"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "UI",
        "name": "University of Ibadan",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                    ("CHM", "Chemistry"),
                    ("PHY", "Physics"),
                    ("MTH", "Mathematics"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [
                    ("MBB", "Medicine & Surgery"),
                    ("NSC", "Nursing Science"),
                    ("PHA", "Pharmacy"),
                ],
            },
        ],
    },
    {
        "code": "OAU",
        "name": "Obafemi Awolowo University",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                    ("CHM", "Chemistry"),
                    ("PHY", "Physics"),
                    ("MTH", "Mathematics"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Pharmacy",
                "duration_years": 5,
                "departments": [("PHA", "Pharmacy")],
            },
        ],
    },
    {
        "code": "UNN",
        "name": "University of Nigeria, Nsukka",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                    ("CHM", "Chemistry"),
                    ("PHY", "Physics"),
                    ("MTH", "Mathematics"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "ABU",
        "name": "Ahmadu Bello University, Zaria",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "UNIBEN",
        "name": "University of Benin",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "LASU",
        "name": "Lagos State University, Ojo",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [("EEE", "Electrical & Electronics Engineering")],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "COVENANT",
        "name": "Covenant University, Ota",
        "colleges": [
            {
                "code": "SCI",
                "name": "College of Science & Technology",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "College of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "College of Business & Social Sciences",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
        ],
    },
    {
        "code": "FUNAAB",
        "name": "Federal University of Agriculture, Abeokuta",
        "colleges": [
            {
                "code": "COLAMRUD",
                "name": "College of Agricultural Management & Rural Development",
                "duration_years": 4,
                "departments": [
                    ("AEE", "Agricultural Economics & Extension"),
                    ("AGRM", "Agricultural Resource Management"),
                    ("RDS", "Rural Development & Sociology"),
                ],
            },
            {
                "code": "COLANIM",
                "name": "College of Animal Science & Livestock Production",
                "duration_years": 5,
                "departments": [
                    ("ANS", "Animal Science"),
                    ("NUT", "Animal Nutrition"),
                    ("BREED", "Animal Breeding & Genetics"),
                ],
            },
            {
                "code": "COLBIOS",
                "name": "College of Biosciences",
                "duration_years": 4,
                "departments": [
                    ("BCH", "Biochemistry"),
                    ("BIO", "Biology"),
                    ("MCB", "Microbiology"),
                    ("PLTBIO", "Plant Biology"),
                ],
            },
            {
                "code": "COLCOMPS",
                "name": "College of Computing Sciences",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("CYB", "Cyber Security"),
                    ("DS", "Data Science"),
                    ("IS", "Information Systems"),
                ],
            },
            {
                "code": "COLENG",
                "name": "College of Engineering",
                "duration_years": 5,
                "departments": [
                    ("CVE", "Civil Engineering"),
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("AGE", "Agricultural Engineering"),
                    ("FPE", "Food Process Engineering"),
                ],
            },
            {
                "code": "COLERM",
                "name": "College of Environmental Resources Management",
                "duration_years": 4,
                "departments": [
                    ("ESM", "Environmental Management"),
                    ("WRM", "Water Resources Management"),
                    ("FWM", "Forestry & Wildlife Management"),
                ],
            },
            {
                "code": "COLFHEC",
                "name": "College of Food Science & Human Ecology",
                "duration_years": 4,
                "departments": [
                    ("FST", "Food Science & Technology"),
                    ("HND", "Home Economics"),
                    ("HM", "Hospitality Management"),
                ],
            },
            {
                "code": "COLPHYS",
                "name": "College of Physical Sciences",
                "duration_years": 4,
                "departments": [
                    ("CHM", "Chemistry"),
                    ("PHY", "Physics"),
                    ("MTH", "Mathematics"),
                    ("STT", "Statistics"),
                ],
            },
            {
                "code": "COLPLANT",
                "name": "College of Plant Science & Crop Production",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Crop Science & Horticulture"),
                    ("PP", "Plant Pathology"),
                    ("SSS", "Soil Science & Land Management"),
                ],
            },
            {
                "code": "COLVET",
                "name": "College of Veterinary Medicine",
                "duration_years": 5,
                "departments": [
                    ("VMD", "Veterinary Medicine"),
                    ("VPH", "Veterinary Public Health"),
                    ("VPT", "Veterinary Pharmacology"),
                ],
            },
            {
                "code": "COLENDS",
                "name": "College of Entrepreneurial & Development Studies",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                    ("ENT", "Entrepreneurship"),
                    ("BNK", "Banking & Finance"),
                ],
            },
        ],
    },
    {
        "code": "UNILORIN",
        "name": "University of Ilorin",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                    ("CHM", "Chemistry"),
                    ("PHY", "Physics"),
                    ("MTH", "Mathematics"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "BOWEN",
        "name": "Bowen University, Iwo",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("EEE", "Electrical & Electronics Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "REDEEMERS",
        "name": "Redeemer's University, Ede",
        "colleges": [
            {
                "code": "SCI",
                "name": "College of Science & Technology",
                "duration_years": 4,
                "departments": [("CSC", "Computer Science")],
            },
            {
                "code": "BUS",
                "name": "College of Management Sciences",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
        ],
    },
    {
        "code": "BUK",
        "name": "Bayero University, Kano",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                ],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "UNIUYO",
        "name": "University of Uyo",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "Faculty of Engineering",
                "duration_years": 5,
                "departments": [("EEE", "Electrical & Electronics Engineering")],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
        ],
    },
    {
        "code": "FUTO",
        "name": "Federal University of Technology, Owerri",
        "colleges": [
            {
                "code": "SCI",
                "name": "School of Science & Technology",
                "duration_years": 4,
                "departments": [("CSC", "Computer Science")],
            },
            {
                "code": "ENG",
                "name": "School of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                    ("MME", "Materials & Metallurgical Engineering"),
                ],
            },
        ],
    },
    {
        "code": "FUTA",
        "name": "Federal University of Technology, Akure",
        "colleges": [
            {
                "code": "SCI",
                "name": "School of Science",
                "duration_years": 4,
                "departments": [
                    ("CSC", "Computer Science"),
                    ("BCH", "Biochemistry"),
                ],
            },
            {
                "code": "ENG",
                "name": "School of Engineering",
                "duration_years": 5,
                "departments": [
                    ("EEE", "Electrical & Electronics Engineering"),
                    ("MEE", "Mechanical Engineering"),
                    ("CVE", "Civil Engineering"),
                ],
            },
        ],
    },
    {
        "code": "UNIMAID",
        "name": "University of Maiduguri",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [("CSC", "Computer Science")],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
            {
                "code": "MED",
                "name": "Faculty of Medicine",
                "duration_years": 6,
                "departments": [("MBB", "Medicine & Surgery")],
            },
        ],
    },
    {
        "code": "LEADCITY",
        "name": "Lead City University, Ibadan",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [("CSC", "Computer Science")],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
        ],
    },
    {
        "code": "NOUN",
        "name": "National Open University of Nigeria",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [("CSC", "Computer Science")],
            },
            {
                "code": "BUS",
                "name": "Faculty of Management Sciences",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("BUS", "Business Administration"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
        ],
    },
    {
        "code": "DELSU",
        "name": "Delta State University, Abraka",
        "colleges": [
            {
                "code": "SCI",
                "name": "Faculty of Science",
                "duration_years": 4,
                "departments": [("CSC", "Computer Science")],
            },
            {
                "code": "BUS",
                "name": "Faculty of Business Administration",
                "duration_years": 4,
                "departments": [
                    ("ACC", "Accounting"),
                    ("ECO", "Economics"),
                ],
            },
            {
                "code": "LAW",
                "name": "Faculty of Law",
                "duration_years": 5,
                "departments": [("LAW", "Law")],
            },
        ],
    },
    # ── NUC-Approved Federal Universities (2026) ────────────────────────────
    # Universities already seeded above are intentionally omitted; the merge
    # logic below skips any university whose normalized name already exists.
    {"code": "ATBU", "name": "Abubakar Tafawa Balewa University"},
    {"code": "ADEYEMI", "name": "Adeyemi Federal University of Education"},
    {"code": "AFIT", "name": "Air Force Institute of Technology"},
    {"code": "AE-FUNAI", "name": "Alex Ekwueme Federal University Ndufu-Alike"},
    {"code": "ALVAN", "name": "Alvan Ikoku Federal University of Education"},
    {"code": "FUBK", "name": "Federal University Birnin Kebbi"},
    {"code": "FUD", "name": "Federal University Dutse"},
    {"code": "FUDMA", "name": "Federal University Dutsin-Ma"},
    {"code": "FUGASHUA", "name": "Federal University Gashua"},
    {"code": "FUGUS", "name": "Federal University Gusau"},
    {"code": "FUKASHERE", "name": "Federal University Kashere"},
    {"code": "FULAFIA", "name": "Federal University Lafia"},
    {"code": "FULOKOJA", "name": "Federal University Lokoja"},
    {"code": "FUAZ", "name": "Federal University of Agriculture, Zuru"},
    {"code": "FUSK", "name": "Federal University of Applied Sciences, Kachia"},
    {"code": "FUEP", "name": "Federal University of Education, Pankshin"},
    {"code": "FUEZ", "name": "Federal University of Education, Zaria"},
    {"code": "FUHSA", "name": "Federal University of Health Sciences, Azare"},
    {"code": "FUPRE", "name": "Federal University of Petroleum Resources, Effurun"},
    {"code": "FUTMINNA", "name": "Federal University of Technology, Minna"},
    {"code": "FUTD", "name": "Federal University of Transportation, Daura"},
    {"code": "FUOTUOKE", "name": "Federal University Otuoke"},
    {"code": "FUOYE", "name": "Federal University Oye-Ekiti"},
    {"code": "FUWUKARI", "name": "Federal University Wukari"},
    {"code": "JOSTUM", "name": "Joseph Sarwuan Tarka University"},
    {"code": "MOUAU", "name": "Michael Okpara University of Agriculture"},
    {"code": "MAUTECH", "name": "Modibbo Adama University of Technology"},
    {"code": "NAUB", "name": "Nigerian Army University, Biu"},
    {"code": "NDA", "name": "Nigerian Defense Academy"},
    {"code": "NMU", "name": "Nigerian Maritime University"},
    {"code": "UNIZIK", "name": "Nnamdi Azikiwe University"},
    {"code": "TASUED", "name": "Tai Solarin Federal University of Education"},
    {"code": "UNIABUJA", "name": "University of Abuja"},
    {"code": "UNICAL", "name": "University of Calabar"},
    {"code": "UNIJOS", "name": "University of Jos"},
    {"code": "UNIPORT", "name": "University of Port Harcourt"},
]

_POLY_SCHOOLS = [
    {
        "code": "ENG",
        "name": "School of Engineering",
        "duration_years": 4,
        "departments": [
            ("CVE", "Civil Engineering Technology"),
            ("EET", "Electrical/Electronic Engineering Technology"),
            ("MCE", "Mechanical Engineering Technology"),
            ("MCT", "Computer Engineering Technology"),
        ],
    },
    {
        "code": "ESC",
        "name": "School of Environmental Studies",
        "duration_years": 4,
        "departments": [
            ("ARC", "Architectural Technology"),
            ("EST", "Estate Management and Valuation"),
            ("QSB", "Quantity Surveying"),
            ("SUR", "Surveying and Geo-informatics"),
        ],
    },
    {
        "code": "ASC",
        "name": "School of Applied Science and Technology",
        "duration_years": 4,
        "departments": [
            ("CPT", "Computer Science"),
            ("SLT", "Science Laboratory Technology"),
            ("STA", "Statistics"),
            ("FST", "Food Science and Technology"),
        ],
    },
    {
        "code": "BMS",
        "name": "School of Business and Management Studies",
        "duration_years": 4,
        "departments": [
            ("ACC", "Accountancy"),
            ("BAM", "Business Administration and Management"),
            ("MKT", "Marketing"),
            ("PUB", "Public Administration"),
        ],
    },
    {
        "code": "LIS",
        "name": "School of Liberal and Communication Studies",
        "duration_years": 4,
        "departments": [
            ("MAC", "Mass Communication"),
            ("OTM", "Office Technology and Management"),
        ],
    },
]

_POLYTECHNIC_SEED_DATA = [
    {"code": code, "name": name, "program_type": "polytechnic",
     "colleges": [dict(s, departments=list(s["departments"])) for s in _POLY_SCHOOLS]}
    for code, name in [
        ("YABATECH", "Yaba College of Technology"),
        ("POLYIBADAN", "The Polytechnic Ibadan"),
        ("KADPOLY", "Kaduna Polytechnic"),
        ("FEDPOLELE", "Federal Polytechnic, Ilaro"),
        ("AUCHIPOLY", "Auchi Polytechnic"),
        ("NEKEDEPOLY", "Federal Polytechnic, Nekede"),
        ("FEDPOLYADO", "Federal Polytechnic, Ado-Ekiti"),
        ("IMTENUGU", "Institute of Management and Technology, Enugu"),
        ("KWARAPOLY", "Kwara State Polytechnic"),
        ("OGUNPOLY", "Ogun State Institute of Technology"),
    ]
]


@router.post("/seed")
async def seed_colleges(
    db: AsyncSession = Depends(get_db),
    _key: str = Depends(verify_maintenance_key),
):
    existing_university_names = {
        _normalize_name(n)
        for n in (await db.execute(select(University.name))).scalars().all()
    }
    existing_catalog_codes = set(
        (await db.execute(select(DepartmentCatalog.code))).scalars().all()
    )

    added = 0
    skipped = 0

    for uni_data in [*SEED_DATA, *_POLYTECHNIC_SEED_DATA]:
        if _normalize_name(uni_data["name"]) in existing_university_names:
            skipped += 1
            continue

        uni_id = str(uuid.uuid4())
        university = University(
            id=uni_id,
            code=uni_data["code"],
            name=uni_data["name"],
            program_type=uni_data.get("program_type", "university"),
        )
        db.add(university)

        for college_data in uni_data.get("colleges", DEFAULT_COLLEGES):
            college_id = str(uuid.uuid4())
            college = College(
                id=college_id,
                code=college_data["code"],
                name=college_data["name"],
                duration_years=college_data.get("duration_years", 4),
                university_id=uni_id,
            )
            db.add(college)

            for dept_code, dept_name in college_data.get("departments", []):
                department = Department(
                    id=str(uuid.uuid4()),
                    code=dept_code,
                    name=dept_name,
                    college_id=college_id,
                )
                db.add(department)

                if dept_code not in existing_catalog_codes:
                    existing_catalog_codes.add(dept_code)
                    db.add(DepartmentCatalog(code=dept_code, name=dept_name))

        added += 1

    await db.commit()
    return {
        "message": f"Seeded {added} new universities (skipped {skipped} already present)"
    }
