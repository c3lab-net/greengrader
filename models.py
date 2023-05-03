##############################################################################
# GreenGrader Object-Relational Mapping Library
# Declares classes mapping to database tables 
# 
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, text, ARRAY, JSON, BIGINT
from sqlalchemy.dialects.postgresql import BYTEA, INET
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Submissions Data Model
class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(BIGINT, primary_key=True)
    submission_id = Column(Integer)
    status = Column(Integer)
    payload = Column(BYTEA)
    sender_ip = Column(INET)
    receiver_ip = Column(INET)
    student_names = Column(ARRAY(String))
    student_emails = Column(ARRAY(String))
    student_ids = Column(ARRAY(Integer))
    student_assignments = Column(ARRAY(JSON))
    created_at = Column(String)
    course_id = Column(Integer)
    assignment_id = Column(Integer)
    assignment_title = Column(String)
    assignment_release_date = Column(String)
    assignment_due_date = Column(String)
    assignment_late_due_date = Column(String)
    assignment_group_submission = Column(Boolean)
    assignment_group_size = Column(Integer)
    assignment_total_points = Column(DECIMAL)
    assignment_outline = Column(ARRAY(JSON))
    submission_method = Column(String)

# Results Data Model
class Results(Base):
    __tablename__ = 'results'
    id = Column(BIGINT, primary_key=True)
    submission_id = Column(Integer)
    server = Column(String)
    visibility = Column(String)
    tests = Column(ARRAY(JSON))
    leaderboard = Column(ARRAY(JSON))
    score = Column(DECIMAL)
    execution_time = Column(DECIMAL)
    total_time = Column(DECIMAL)
    execution_power = Column(DECIMAL)
    carbon_intensity = Column(DECIMAL)

# Workers Data Model
class Workers(Base):
    __tablename__ = 'workers'
    id = Column(BIGINT, primary_key=True)
    ip = Column(INET)
    name = Column(String)
    cpu_model_name = Column(String)
    cpu_clock_rate = Column(DECIMAL)
    cpu_sockets = Column(Integer)
    cpu_cores = Column(Integer)
    cache_size = Column(Integer)
    memory_size = Column(Integer)

# Assignments Data Model
class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True)
    version = Column(String)

