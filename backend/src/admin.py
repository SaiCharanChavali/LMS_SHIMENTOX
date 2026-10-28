"""Role-protected account provisioning, course authoring, and admin audit records."""
import json
import re
from urllib.parse import parse_qs, urlsplit

from database import COURSE_ID, CURRICULUM, LESSONS
from security import password_hash, verify_password
from services import ROLES, allowed, check, require, text, uid, now, create_run, candidate_view, records, expire_exams

DIFFICULTIES = ('beginner', 'intermediate', 'advanced', 'expert')


def audit(db, admin, action, target, detail=''):
    db.execute('INSERT INTO admin_events(admin_id,action,target_id,detail,created_at) VALUES (?,?,?,?,?)', (admin,action,target,detail,now()))


def setup_initial_admin(db,data):
    check(db.execute("SELECT 1 FROM candidates WHERE role='admin'").fetchone() is None,'Administrator setup has already been completed.',409)
    name,email,password=text(data,'name',2,100),text(data,'email').casefold(),text(data,'password',8,128)
    check(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) is not None,'Enter a valid email address.')
    existing=db.execute('SELECT * FROM candidates WHERE email=?',(email,)).fetchone()
    if existing:
        check(existing['is_active'] and verify_password(password,existing['password_hash']),'This email already exists. Enter its current password to use it for admin setup.',403)
        identity=existing['id']
        db.execute("UPDATE candidates SET role='admin',must_change_password=0,updated_at=? WHERE id=?",(now(),identity))
        db.execute('DELETE FROM sessions WHERE candidate_id=?',(identity,))
    else:
        identity=uid()
        db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES (?,?,?,?,?,?,'admin')",(identity,name,email,password_hash(password),now(),now()))
        create_run(db,identity)
    audit(db,identity,'admin_setup',identity,'First administrator configured from the local setup page')


def optional_id(db, data, field, table, label, condition=''):
    value=data.get(field) or None
    if value is not None:
        check(isinstance(value,str) and db.execute(f'SELECT 1 FROM {table} WHERE id=? {condition}',(value,)).fetchone() is not None,f'Select a valid {label}.')
    return value


def role_input(data, actor):
    role=data.get('role','employee')
    if role=='candidate':role='employee'  # Accept the pre-v3 API value.
    check(role in ROLES,'Invalid role.')
    check(actor['role']=='admin' or role!='admin','Only administrators can grant administrator access.',403)
    return role


def org_fields(db, data, identity=None):
    department=optional_id(db,data,'departmentId','departments','department')
    job_role=optional_id(db,data,'jobRoleId','job_roles','job role')
    manager=optional_id(db,data,'managerId','candidates','manager','AND is_active=1')
    check(manager is None or manager!=identity,'An employee cannot be their own manager.')
    title=data.get('jobTitle','')
    check(isinstance(title,str) and len(title.strip())<=100,'Job title must contain at most 100 characters.')
    return department,job_role,manager,title.strip()


def provision(db, actor, data):
    name, email, password = text(data,'name',2,100), text(data,'email').casefold(), text(data,'password',8,128)
    check(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) is not None,'Enter a valid email address.')
    role=role_input(data,actor)
    department,job_role,manager,title=org_fields(db,data)
    check(db.execute('SELECT 1 FROM candidates WHERE email=?',(email,)).fetchone() is None,'This email is already assigned.',409)
    identity,timestamp=uid(),now()
    db.execute('INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role,must_change_password,created_by,department_id,job_role_id,manager_id,job_title) VALUES (?,?,?,?,?,?,?,1,?,?,?,?,?)',(identity,name,email,password_hash(password),timestamp,timestamp,role,actor['id'],department,job_role,manager,title))
    create_run(db,identity)
    audit(db,actor['id'],'employee_created',identity,f'{role}: {email}')
    return candidate_view(db.execute('SELECT * FROM candidates WHERE id=?',(identity,)).fetchone())


def update_profile(db, actor, target, data):
    name=text(data,'name',2,100)
    role=role_input(data,actor)
    check(target['id']!=actor['id'] or role==target['role'],'You cannot change your own role.')
    department,job_role,manager,title=org_fields(db,data,target['id'])
    db.execute('UPDATE candidates SET full_name=?,role=?,department_id=?,job_role_id=?,manager_id=?,job_title=?,updated_at=? WHERE id=?',(name,role,department,job_role,manager,title,now(),target['id']))
    audit(db,actor['id'],'employee_updated',target['id'],f'{role}: {target["email"]}')
    return candidate_view(db.execute('SELECT * FROM candidates WHERE id=?',(target['id'],)).fetchone())


def candidate_list(db):
    users=[]
    rows=db.execute('''SELECT c.*,d.name AS department,j.name AS job_role,m.full_name AS manager,
        (SELECT COUNT(*) FROM certificates x JOIN course_runs r ON r.id=x.run_id WHERE r.candidate_id=c.id) AS certificate_count,
        (SELECT COUNT(*) FROM course_runs r WHERE r.candidate_id=c.id) AS run_count
        FROM candidates c LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN job_roles j ON j.id=c.job_role_id LEFT JOIN candidates m ON m.id=c.manager_id
        ORDER BY c.created_at DESC,c.id''')
    for row in rows:
        item=candidate_view(row)
        item.update({'certificates':row['certificate_count'],'courseRuns':row['run_count'],'lastLoginAt':row['last_login_at'],'department':row['department'],'jobRole':row['job_role'],'manager':row['manager']})
        users.append(item)
    return users


def course_skills(db, course_id):
    return [{'id':r['id'],'name':r['name'],'level':r['level']} for r in db.execute('SELECT s.id,s.name,k.level FROM course_skills k JOIN skills s ON s.id=k.skill_id WHERE k.course_id=? ORDER BY s.name',(course_id,))]


def course_view(row, private=False, db=None):
    result={key:row[key] for key in ('id','title','description','category','status','version')}
    keys=row.keys()
    if 'difficulty' in keys:
        result.update({'difficulty':row['difficulty'],'durationMinutes':row['duration_minutes'],'departmentId':row['department_id'],'trainerId':row['trainer_id'],
                       'passPercent':row['pass_percent'],'maxAttempts':row['max_attempts'],'postAssessmentId':row['post_assessment_id']})
    if 'format' in keys:
        result.update({'format':row['format'],'visibility':row['visibility']})
    if 'page_layout' in keys:
        result['layout']=row['page_layout']
    if 'source_url' in keys and row['source_url']:
        # Imported courses always show where the content came from.
        result['source']={'url':row['source_url'],'platform':row['source_platform'],'importStatus':row['import_status']}
        if private and row['import_report_json']:result['importReport']=json.loads(row['import_report_json'])
    if db is not None:
        result['skills']=course_skills(db,row['id'])
        department=db.execute('SELECT name FROM departments WHERE id=?',(result.get('departmentId'),)).fetchone()
        result['department']=department[0] if department else None
    if private:
        result['content']={'sets':json.loads(row['sets_json']),'lessons':json.loads(row['lessons_json'])}
        if db is not None:
            result['learners']=db.execute('SELECT COUNT(DISTINCT candidate_id) FROM course_runs WHERE course_id=?',(row['id'],)).fetchone()[0]
            result['hasLearners']=bool(result['learners'])
            result['resources']=[dict(r) for r in db.execute('SELECT id,module_index,title,kind,url FROM course_resources WHERE course_id=? ORDER BY created_at',(row['id'],))]
            result['assignments']=db.execute('SELECT COUNT(*) FROM course_assignments WHERE course_id=?',(row['id'],)).fetchone()[0]
    return result


def owns_course(actor, row):
    return actor['role'] in ('admin','hr') or actor['id'] in (row['trainer_id'],row['created_by'])


def course_list(db, actor):
    """Enrich a role-scoped catalog with four queries, independent of its size."""
    where,params=('1=1',()) if actor['role'] in ('admin','hr') else ('(k.trainer_id=? OR k.created_by=?)',(actor['id'],actor['id']))
    skills,resources,assignments={},{},{}
    for row in db.execute(f'SELECT q.course_id,s.id,s.name,q.level FROM course_skills q JOIN courses k ON k.id=q.course_id JOIN skills s ON s.id=q.skill_id WHERE {where} ORDER BY s.name',params):
        skills.setdefault(row['course_id'],[]).append({'id':row['id'],'name':row['name'],'level':row['level']})
    for row in db.execute(f'SELECT q.course_id,q.id,q.module_index,q.title,q.kind,q.url FROM course_resources q JOIN courses k ON k.id=q.course_id WHERE {where} ORDER BY q.created_at,q.rowid',params):
        resources.setdefault(row['course_id'],[]).append({key:row[key] for key in ('id','module_index','title','kind','url')})
    for row in db.execute(f'SELECT q.course_id,COUNT(*) FROM course_assignments q JOIN courses k ON k.id=q.course_id WHERE {where} GROUP BY q.course_id',params):
        assignments[row[0]]=row[1]
    result=[]
    for row in db.execute(f'SELECT k.*,d.name AS department_name,(SELECT COUNT(DISTINCT r.candidate_id) FROM course_runs r WHERE r.course_id=k.id) AS learners FROM courses k LEFT JOIN departments d ON d.id=k.department_id WHERE {where} ORDER BY k.title',params):
        item=course_view(row,True)
        item.update({'skills':skills.pop(row['id'],[]),'department':row['department_name'],'hasLearners':bool(row['learners']),'learners':row['learners'],'resources':resources.pop(row['id'],[]),'assignments':assignments.pop(row['id'],0)})
        result.append(item)
    return result


def media_reference(value):
    parsed=urlsplit(value)
    return (parsed.scheme=='https' and parsed.netloc and not parsed.username and not parsed.password) or (not parsed.scheme and not parsed.netloc and (value.startswith('assets/') or re.fullmatch(r'api/materials/[0-9a-f-]{36}',value) is not None) and '..' not in value.split('/'))


def validate_content(content):
    check(isinstance(content,dict),'Course content must be a JSON object.')
    sets,lessons=content.get('sets'),content.get('lessons')
    check(isinstance(sets,list) and len(sets)==3,'A course requires exactly 3 modules.')
    check(isinstance(lessons,list) and len(lessons)==6,'A course requires exactly 6 video lessons.')
    for i,lesson in enumerate(lessons):
        check(isinstance(lesson,dict),f'Invalid lesson {i+1}.')
        text(lesson,'title',2,150)
        for field in ('body','code','task'):
            check(isinstance(lesson.get(field),str) and len(lesson[field])<=12000,f'Lesson {i+1}: {field} text is required.')
        for field in ('src','captions'):
            value=lesson.get(field,'')
            if field=='captions' and not value: continue
            check(isinstance(value,str) and len(value)<=2000,f'Invalid lesson {field}.')
            check(media_reference(value),f'Lesson {field} must be an assets/ path, an uploaded material, or an HTTPS URL.')
        duration=lesson.get('duration')
        check(type(duration) in (int,float) and 1<=duration<=7200,'Video duration must be between 1 and 7200 seconds.')
    for s,item in enumerate(sets):
        check(isinstance(item,dict),'Invalid course module.')
        text(item,'title',2,150);text(item,'summary',1,1000)
        check(item.get('videos')==[s*2,s*2+1],'Each module must reference its two sequential video indices.')
        exercises=item.get('exercises')
        check(isinstance(exercises,list) and len(exercises)==2,'Every module requires exactly 2 exercises.')
        groups=[]
        for exercise in exercises:
            check(isinstance(exercise,dict),'Invalid exercise.')
            text(exercise,'title',2,150)
            groups.append((exercise.get('questions'),2,True))
        groups.append((item.get('exam'),4,False))
        for questions,count,practice in groups:
            check(isinstance(questions,list) and len(questions)==count,f'Expected {count} questions.')
            for q in questions:
                check(isinstance(q,list) and len(q)>=(4 if practice else 3),'Invalid question format.')
                check(isinstance(q[0],str) and 1<=len(q[0])<=2000,'Question text is required.')
                check(isinstance(q[1],list) and 2<=len(q[1])<=6 and all(isinstance(o,str) and 1<=len(o)<=1000 for o in q[1]),'Provide 2-6 non-empty answer options.')
                check(type(q[2]) is int and 0<=q[2]<len(q[1]),'Question has an invalid correct-answer index.')
                if practice: check(isinstance(q[3],str) and len(q[3])<=2000,'Practice feedback is required.')
    return sets,lessons


def course_metadata(db, data, old):
    """Training metadata; missing fields keep their stored (or default) values."""
    def value(field, column, default):
        return data[field] if field in data else (old[column] if old else default)
    difficulty=value('difficulty','difficulty','beginner');check(difficulty in DIFFICULTIES,'Select a valid difficulty level.')
    duration=value('durationMinutes','duration_minutes',0);check(type(duration) is int and 0<=duration<=100000,'Estimated duration must be a whole number of minutes.')
    pass_percent=value('passPercent','pass_percent',75);check(type(pass_percent) is int and 25<=pass_percent<=100,'Passing score must be between 25 and 100%.')
    attempts=value('maxAttempts','max_attempts',3);check(type(attempts) is int and 1<=attempts<=3,'Exam attempts per module must be between 1 and 3.')
    department=optional_id(db,{'d':value('departmentId','department_id',None)},'d','departments','department')
    trainer=optional_id(db,{'t':value('trainerId','trainer_id',None)},'t','candidates','trainer',"AND role IN ('admin','hr','trainer') AND is_active=1")
    post=optional_id(db,{'p':value('postAssessmentId','post_assessment_id',None)},'p','assessments','post-training assessment',"AND kind='post'")
    return difficulty,duration,pass_percent,attempts,department,trainer,post


def save_skills(db, course_id, skills):
    check(isinstance(skills,list) and len(skills)<=20,'Select up to 20 skills.')
    seen=set()
    for item in skills:
        check(isinstance(item,dict) and isinstance(item.get('skillId'),str) and type(item.get('level')) is int and 1<=item['level']<=4,'Each skill tag needs a skill and a level from 1 to 4.')
        check(item['skillId'] not in seen and db.execute('SELECT 1 FROM skills WHERE id=?',(item['skillId'],)).fetchone() is not None,'Select valid, distinct skills.')
        seen.add(item['skillId'])
    db.execute('DELETE FROM course_skills WHERE course_id=?',(course_id,))
    for item in skills:db.execute('INSERT INTO course_skills VALUES (?,?,?)',(course_id,item['skillId'],item['level']))


VIDEO_FILE = re.compile(r'\.(mp4|webm|ogg|m4v)$', re.I)


def embed_video(value):
    """Permitted embeds become official embed URLs; other video must be an upload, an assets/ file, or a direct HTTPS video file."""
    parsed=urlsplit(value);host=(parsed.hostname or '').lower();segments=[s for s in parsed.path.split('/') if s]
    if host in ('youtu.be','youtube.com','www.youtube.com','m.youtube.com','www.youtube-nocookie.com'):
        video=segments[0] if host=='youtu.be' and segments else parse_qs(parsed.query).get('v',[''])[0] if parsed.path=='/watch' else segments[1] if len(segments)>1 and segments[0] in ('embed','shorts','live') else ''
        check(re.fullmatch(r'[A-Za-z0-9_-]{6,20}',video or '') is not None,'Enter a valid YouTube video link.')
        return f'https://www.youtube-nocookie.com/embed/{video}'
    if host in ('vimeo.com','www.vimeo.com','player.vimeo.com'):
        video=next((s for s in reversed(segments) if s.isdigit()),'')
        check(bool(video),'Enter a valid Vimeo video link.')
        return f'https://player.vimeo.com/video/{video}'
    check(media_reference(value) and (not parsed.scheme or VIDEO_FILE.search(parsed.path) is not None),'Use a YouTube or Vimeo link, an uploaded video, or a direct HTTPS .mp4/.webm video link.')
    return value


def lesson_text(item, key, maximum, label, number, minimum=0):
    value=item.get(key) or ''
    check(isinstance(value,str) and minimum<=len(value.strip())<=maximum,f'Lesson {number}: {label} must contain {minimum}–{maximum} characters.' if minimum else f'Lesson {number}: {label} must contain at most {maximum} characters.')
    return value.strip()


def lesson_input(db, item, number):
    check(isinstance(item,dict),f'Lesson {number} is invalid.')
    lesson={'title':lesson_text(item,'title',150,'the title',number,2),'description':lesson_text(item,'description',2000,'the description',number),
            'content':lesson_text(item,'content',100000,'the learning content',number),'exercise':lesson_text(item,'exercise',5000,'the practical exercise',number)}
    video=lesson_text(item,'videoUrl',2000,'the video link',number)
    lesson['video_url']=embed_video(video) if video else ''
    document=lesson_text(item,'documentUrl',2000,'the document link',number)
    material=re.fullmatch(r'api/materials/([0-9a-f-]{36})',document)
    check(not document or (media_reference(document) and (material is None or db.execute('SELECT 1 FROM materials WHERE id=?',(material.group(1),)).fetchone() is not None)),f'Lesson {number}: the document must be an uploaded file or an HTTPS link.')
    lesson['document_url']=document
    lesson['document_name']=lesson_text(item,'documentName',200,'the document name',number) if document else ''
    resources=item.get('resources') or []
    check(isinstance(resources,list) and len(resources)<=20,f'Lesson {number}: add up to 20 external resources.')
    clean=[]
    for resource in resources:
        check(isinstance(resource,dict),f'Lesson {number}: invalid external resource.')
        url=lesson_text(resource,'url',2000,'each resource link',number,1)
        parsed=urlsplit(url)
        check(parsed.scheme=='https' and parsed.netloc and not parsed.username and not parsed.password,f'Lesson {number}: external resources must be HTTPS links.')
        clean.append({'title':lesson_text(resource,'title',150,'each resource title',number,2),'url':url})
    lesson['resources_json']=json.dumps(clean)
    duration=item.get('durationMinutes',0)
    check(type(duration) is int and 0<=duration<=1000,f'Lesson {number}: duration must be a whole number of minutes from 0 to 1000.')
    lesson['duration_minutes']=duration
    # Optional video settings; when a field is not sent, the stored value is kept (see save_lessons).
    if 'captionsUrl' in item:
        captions=lesson_text(item,'captionsUrl',2000,'the captions link',number)
        check(not captions or (media_reference(captions) and urlsplit(captions).path.lower().endswith('.vtt')),f'Lesson {number}: captions must be a WebVTT (.vtt) file.')
        lesson['captions_url']=captions
    if 'videoSeconds' in item:
        seconds=item.get('videoSeconds') or 0
        check(type(seconds) in (int,float) and 0<=seconds<=36000,f'Lesson {number}: video length must be between 0 and 36000 seconds.')
        lesson['video_seconds']=float(seconds)
    if 'completionPercent' in item:
        percent=item.get('completionPercent')
        check(type(percent) is int and 50<=percent<=100,f'Lesson {number}: the completion threshold must be a whole percentage from 50 to 100.')
        lesson['completion_percent']=percent
    return lesson


def save_lessons(db, course_id, lessons):
    """Persist the ordered lesson list. Lessons that employees have completed cannot be removed."""
    check(isinstance(lessons,list) and len(lessons)<=100,'A course can have up to 100 lessons.')
    existing={r['id']:r['title'] for r in db.execute('SELECT id,title FROM course_lessons WHERE course_id=?',(course_id,))}
    kept=set()
    for position,item in enumerate(lessons):
        lesson=lesson_input(db,item,position+1)
        identity=item.get('id') if item.get('id') in existing and item.get('id') not in kept else None
        columns=dict(lesson,position=position,updated_at=now())
        if identity:
            db.execute(f"UPDATE course_lessons SET {','.join(f'{c}=?' for c in columns)} WHERE id=?",(*columns.values(),identity))
        else:
            identity=uid()
            columns.update(id=identity,course_id=course_id,created_at=columns['updated_at'])
            db.execute(f"INSERT INTO course_lessons({','.join(columns)}) VALUES ({','.join('?'*len(columns))})",tuple(columns.values()))
        kept.add(identity)
    for identity in set(existing)-kept:
        used=any(db.execute(f'SELECT 1 FROM {table} WHERE lesson_id=? LIMIT 1',(identity,)).fetchone() for table in ('lesson_progress','lesson_watch','lesson_activity_attempts'))
        check(not used,f'“{existing[identity]}” has employee progress and cannot be removed. Edit it instead, or archive this course and create a new version.',409)
        db.execute('DELETE FROM course_lessons WHERE id=?',(identity,))


def check_publishable(db, course_id):
    lessons=db.execute('SELECT title,video_url,document_url,resources_json,content FROM course_lessons WHERE course_id=? ORDER BY position',(course_id,)).fetchall()
    check(lessons,'Add at least one lesson before publishing.')
    for number,lesson in enumerate(lessons,1):
        check(lesson['video_url'] or lesson['document_url'] or lesson['content'] or json.loads(lesson['resources_json']),f'Lesson {number} (“{lesson["title"]}”) needs a video, document, resource link, or learning content before publishing.')


def save_course(db, actor, data):
    title=text(data,'title',2,150);category=text(data,'category',2,80);description=text(data,'description',1,2000)
    check(db.execute('SELECT 1 FROM course_categories WHERE name=?',(category,)).fetchone() is not None,'Select a configured course category.')
    status=data.get('status','draft');check(status in ('draft','published','archived'),'Invalid course status.')
    identity=data.get('id') or uid()
    check(isinstance(identity,str) and len(identity)<=100,'Invalid course ID.')
    old=db.execute('SELECT * FROM courses WHERE id=?',(identity,)).fetchone()
    if old: check(owns_course(actor,old),'Trainers can edit only the courses they own.',403)
    difficulty,duration,pass_percent,attempts,department,trainer,post=course_metadata(db,data,old)
    if actor['role']=='trainer' and not old: trainer=actor['id']
    # Existing courses keep the 3-module format; new lesson-based courses are built step by step in Manage Courses.
    course_format=old['format'] if old else data.get('format','modules')
    check(course_format in ('modules','lessons') and data.get('format',course_format)==course_format,'A course format cannot be changed after the course is created.')
    visibility=data.get('visibility',old['visibility'] if old else 'everyone')
    check(visibility in ('everyone','department'),'Select a valid visibility setting.')
    check(visibility=='everyone' or department,'Select a department for department-only visibility.')
    has_history=old is not None and db.execute('SELECT 1 FROM course_runs WHERE course_id=?',(identity,)).fetchone() is not None
    if course_format=='modules':
        content=data.get('content')
        if content is None: content={'sets':CURRICULUM,'lessons':LESSONS} if old is None else {'sets':json.loads(old['sets_json']),'lessons':json.loads(old['lessons_json'])}
        sets,lessons=validate_content(content)
        if has_history:
            check(json.loads(old['sets_json'])==sets and json.loads(old['lessons_json'])==lessons,'This course has learner history. Create a new course version to change its lessons or questions.',409)
    else:
        sets,lessons=[],[]
    if old:
        db.execute('UPDATE courses SET title=?,category=?,description=?,status=?,sets_json=?,lessons_json=?,updated_at=?,difficulty=?,duration_minutes=?,pass_percent=?,max_attempts=?,department_id=?,trainer_id=?,post_assessment_id=?,visibility=? WHERE id=?',(title,category,description,status,json.dumps(sets),json.dumps(lessons),now(),difficulty,duration,pass_percent,attempts,department,trainer,post,visibility,identity))
    else:
        db.execute('INSERT INTO courses(id,title,version,category,description,status,sets_json,lessons_json,created_by,updated_at,difficulty,duration_minutes,pass_percent,max_attempts,department_id,trainer_id,post_assessment_id,format,visibility) VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(identity,title,category,description,status,json.dumps(sets),json.dumps(lessons),actor['id'],now(),difficulty,duration,pass_percent,attempts,department,trainer,post,course_format,visibility))
    if 'skills' in data: save_skills(db,identity,data['skills'])
    if course_format=='lessons':
        if 'lessons' in data: save_lessons(db,identity,data['lessons'])
        if 'assessment' in data:
            from development import save_course_assessment  # Local import: development builds on this module.
            db.execute('UPDATE courses SET post_assessment_id=? WHERE id=?',(save_course_assessment(db,actor,identity,title,data['assessment'],status),identity))
        if status=='published': check_publishable(db,identity)
    elif not has_history:
        db.execute('DELETE FROM assessment_questions WHERE course_id=?',(identity,))
        db.execute('DELETE FROM videos WHERE course_id=?',(identity,))
        db.execute('DELETE FROM course_sets WHERE course_id=?',(identity,))
        for s,item in enumerate(sets):
            db.execute('INSERT INTO course_sets VALUES (?,?,?)',(identity,s,item['title']))
            for i in item['videos']: db.execute('INSERT INTO videos VALUES (?,?,?,?)',(identity,i,s,lessons[i]['duration']))
            groups=[('exam',-1,item['exam'])]+[('exercise',e,x['questions']) for e,x in enumerate(item['exercises'])]
            for kind,e,questions in groups:
                for i,q in enumerate(questions): db.execute('INSERT INTO assessment_questions VALUES (?,?,?,?,?,?,?,?,?)',(identity,s,kind,e,i,q[0],json.dumps(q[1]),q[2],q[3] if len(q)>3 else ''))
    if status=='published' and (old is None or old['status']!='published'):
        from notifications import published
        published(db,identity,title)
    audit(db,actor['id'],'course_saved',identity,f'{status}: {title}')
    return course_view(db.execute('SELECT * FROM courses WHERE id=?',(identity,)).fetchone(),True,db)


def archive_course(db, actor, course_id):
    """Hide a course from catalogs while keeping every learner record and certificate."""
    row=db.execute('SELECT * FROM courses WHERE id=?',(course_id,)).fetchone()
    check(row is not None,'Course was not found.',404)
    check(owns_course(actor,row),'Trainers can archive only the courses they own.',403)
    db.execute("UPDATE courses SET status='archived',updated_at=? WHERE id=?",(now(),course_id))
    audit(db,actor['id'],'course_archived',course_id,row['title'])
    return {'ok':True}


def delete_course(db, actor, course_id):
    """Permanently remove a course nobody has started, with its lessons, assessments, assignments and path entries.

    Courses with learner history are archived instead, so employees keep their progress and certificates.
    The ID is recorded so packaged courses are not re-created when the server starts.
    """
    row=db.execute('SELECT * FROM courses WHERE id=?',(course_id,)).fetchone()
    check(row is not None,'Course was not found.',404)
    check(owns_course(actor,row),'Trainers can delete only the courses they own.',403)
    check(course_id!=COURSE_ID,'This is the starter course every new employee is enrolled in, so it cannot be deleted. Archive it to hide it from the catalog.',409)
    learners=db.execute('SELECT COUNT(DISTINCT candidate_id) FROM course_runs WHERE course_id=?',(course_id,)).fetchone()[0]
    assessments=[r[0] for r in db.execute('SELECT id FROM assessments WHERE course_id=? OR id=?',(course_id,row['post_assessment_id']))]
    marks=('?,'*len(assessments)).rstrip(',')
    attempts=db.execute(f'SELECT COUNT(DISTINCT employee_id) FROM assessment_attempts WHERE assessment_id IN ({marks})',assessments).fetchone()[0] if assessments else 0
    people=max(learners,attempts)
    check(not people,f'{people} employee{"" if people==1 else "s"} {"has" if people==1 else "have"} records in this course. Archive it instead: it disappears from catalogs, and their progress and certificates are kept.',409)
    db.execute('UPDATE courses SET post_assessment_id=NULL WHERE id=?',(course_id,))
    db.execute('UPDATE course_lessons SET assessment_id=NULL WHERE course_id=?',(course_id,))
    db.execute('UPDATE training_sessions SET course_id=NULL WHERE course_id=?',(course_id,))
    # Explicit deletes: databases upgraded from early versions lack some cascading foreign keys.
    for table in ('course_lessons','course_checkpoints','course_content_updates','course_skills','course_assignments','learning_path_courses',
                  'course_resources','assessment_questions','videos','course_sets'):
        db.execute(f'DELETE FROM {table} WHERE course_id=?',(course_id,))
    if assessments:
        db.execute(f'DELETE FROM assessment_bank WHERE assessment_id IN ({marks})',assessments)
        db.execute(f'DELETE FROM assessments WHERE id IN ({marks})',assessments)
    db.execute('DELETE FROM courses WHERE id=?',(course_id,))
    db.execute('INSERT OR REPLACE INTO deleted_courses VALUES (?,?,?,?)',(course_id,row['title'],actor['id'],now()))
    audit(db,actor['id'],'course_deleted',course_id,row['title'])
    return {'ok':True}


def protected_target(actor, target):
    # HR manages employee accounts but cannot change administrator accounts.
    check(actor['role']=='admin' or target['role']!='admin','Only administrators can change administrator accounts.',403)


def admin_action(db, actor, method, route, data):
    identity=actor['id']
    if method=='GET' and route=='overview':
        require(actor,'users.manage')
        employees=db.execute("SELECT COUNT(*) FROM candidates WHERE role<>'admin'").fetchone()[0]
        return {'stats':{'employees':employees,'candidates':employees, 'courses':db.execute('SELECT COUNT(*) FROM courses').fetchone()[0], 'certificates':db.execute('SELECT COUNT(*) FROM certificates').fetchone()[0], 'exams':db.execute('SELECT COUNT(*) FROM exam_attempts').fetchone()[0]}}
    if method=='GET' and route=='candidates': require(actor,'users.manage');return {'candidates':candidate_list(db)}
    if method=='POST' and route=='candidates': require(actor,'users.manage');return {'candidate':provision(db,actor,data)}
    if method=='GET' and route=='courses':
        require(actor,'courses.manage')
        return {'courses':course_list(db,actor)}
    if method=='POST' and route=='courses': require(actor,'courses.manage');return {'course':save_course(db,actor,data)}
    if method=='GET' and route=='audit': require(actor,'audit.view');return {'events':[dict(r) for r in db.execute('SELECT a.*,c.full_name AS admin_name FROM admin_events a JOIN candidates c ON c.id=a.admin_id ORDER BY a.id DESC LIMIT 100')]}
    parts=route.split('/')
    if method=='POST' and len(parts)==3 and parts[0]=='courses' and parts[2]=='delete':
        require(actor,'courses.manage');return delete_course(db,actor,parts[1])
    if method=='POST' and len(parts)==3 and parts[0]=='courses' and parts[2]=='archive':
        require(actor,'courses.manage');return archive_course(db,actor,parts[1])
    if len(parts)==3 and parts[0]=='candidates':
        target=db.execute('SELECT * FROM candidates WHERE id=?',(parts[1],)).fetchone();check(target is not None,'Employee was not found.',404)
        if method=='GET' and parts[2]=='records':
            check(allowed(actor,'users.manage') or (actor['role']=='manager' and target['manager_id']==identity),'You can view records only for employees you manage.',403)
            return {'user':candidate_view(target),**records(db,target['id'])}
        require(actor,'users.manage');protected_target(actor,target)
        if method=='POST' and parts[2]=='profile':return {'candidate':update_profile(db,actor,target,data)}
        if method=='POST' and parts[2]=='reset-password':
            check(target['id']!=identity,'Use My profile to change your own password.')
            password=text(data,'password',8,128)
            db.execute('UPDATE candidates SET password_hash=?,must_change_password=1,updated_at=? WHERE id=?',(password_hash(password),now(),target['id']))
            db.execute('DELETE FROM sessions WHERE candidate_id=?',(target['id'],))
            for run in db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND archived_at IS NULL',(target['id'],)).fetchall():expire_exams(db,run['id'],'An administrator reset the account password.')
            audit(db,identity,'password_reset',target['id'])
            return {'ok':True}
        if method=='POST' and parts[2]=='status':
            check(target['id']!=identity,'You cannot disable your own account.')
            check(type(data.get('active')) is bool,'An active status is required.')
            db.execute('UPDATE candidates SET is_active=?,updated_at=? WHERE id=?',(int(data['active']),now(),target['id']))
            if not data['active']:
                db.execute('DELETE FROM sessions WHERE candidate_id=?',(target['id'],))
                for run in db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND archived_at IS NULL',(target['id'],)).fetchall():expire_exams(db,run['id'],'The account was disabled by an administrator.')
            audit(db,identity,'account_status',target['id'],str(data['active']))
            return {'ok':True}
    check(False,'Admin endpoint was not found.',404)
