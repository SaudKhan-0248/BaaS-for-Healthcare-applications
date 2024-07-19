from pydantic import BaseModel
from datetime import date, time
from typing import Literal, Optional


class Patient(BaseModel):
    firstname: str
    lastname: str
    dob: date
    gender: Literal['MALE', 'FEMALE']
    blood_group: Optional[Literal['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']] = None
    contact_no: str
    

class PatientUpdate(BaseModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[Literal["MALE", "FEMALE"]] = None
    blood_group: Optional[Literal['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']] = None
    contact_no: Optional[str] = None


class Doctor(BaseModel):
    name: str
    dob: date
    gender: Literal['MALE', 'FEMALE']
    contact_no: str
    job_title: str
    speciality: str
    qualification: str
    

class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[Literal['MALE', 'FEMALE']] = None
    contact_no: Optional[str] = None
    job_title: Optional[str] = None
    speciality: Optional[str] = None
    qualification: Optional[str] = None


class OpdRecord(BaseModel):
    doctor: str
    disease_description: Optional[str] = None
    primary_diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    date: date
    time: time
    
    
class IpdRecord(BaseModel):
    admission_date: date
    discharge_date: date
    chief_complaint: str
    room_no: Optional[int] = None
    ward_no: Optional[int] = None


class ErRecord(BaseModel):
    doctor: Optional[str] = None
    date: date
    arrival_time: time
    chief_complaint: str

    
class Appointment(BaseModel):
    patient_id: str
    doctor_id: str
    date: date
    status: Literal["pending", "done", "cancelled"] = "pending"
    