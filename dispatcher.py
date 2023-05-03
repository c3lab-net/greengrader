##############################################################################
# GreenGrader Dispatcher
# Checks database on timed interval for new jobs, then schedules them for
# execution on cluster
#
# Authors: Malcolm McSwain, Joshua Santillan
##############################################################################

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from models import Submission
import subprocess
import sys 

# Create a database engine
with open('db_secret.txt') as f:
    secret = f.read()
    engine = create_engine(secret[:-1])
    conn = engine.connect()

# Create a database session
Session = sessionmaker(bind=engine)
session = Session()

# Read command line arguments
args = sys.argv

# Checks database for available work and feeds it to the scheduler
def check_jobs():

    # Fetch the first submission with status 0
    #TODO Curious -> what if i have a job that gets added late but needs to be priortized to run earlier, special flag? -1 maybe? Is this a thought we are considering? delete this comment thanks
    if len(args) > 1:
        assignment_id = int(args[1])
        submission_id = int(args[2])
        
        # Fetch specific submission
        submission = session.query(Submission).filter(Submission.submission_id == submission_id, Submission.assignment_id == assignment_id).first()
        
        if submission:

            # Unzip submission
            with open('gradescope_data.zip', 'wb') as f:
                f.write(submission.payload)
            print('Spawning child...')
            subprocess.run(['unzip', 'gradescope_data.zip'], check=True)

            print("Found required submission, spawning child process...")

            # Call pod.sh with specific submission
            child = subprocess.Popen(['./pod.sh', args[1], args[2]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, err = child.communicate()
            print(output)
            print(err)
        else:
            print('Required submission not found')
            return

    else:
        submission = session.query(Submission).filter(Submission.status == 0).order_by(Submission.created_at.desc()).first()
        if submission:

            # Unzip submission
            with open('gradescope_data.zip', 'wb') as f:
                f.write(submission.payload)
            print('Spawning child...')
            subprocess.run(['unzip', 'gradescope_data.zip'], check=True)

            # Run the execution pipeline 
            child = subprocess.Popen(['./pod.sh', str(submission.assignment_id), str(submission.submission_id)], stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            output, err = child.communicate()
            print(output)
            print(err)

            # Update submission status in database
            # TODO - Conditional status update based on the result of pod.sh
            submission.status = 1
            session.commit()

    # Close database session
    session.close()

def run():
    check_jobs()

if __name__ == '__main__':
    run()
