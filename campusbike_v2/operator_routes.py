"""Administrator account tools and read-only exports."""
import csv
import io
import re
from contextlib import closing
from flask import Response, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash


def register_operator_routes(app, get_db, admin_required):
    @app.route('/admin/accounts',methods=['GET','POST'])
    @admin_required
    def admin_accounts():
        with closing(get_db()) as db:
            if request.method=='POST':
                student_id=request.form.get('student_id','').strip().upper()
                action=request.form.get('action','')
                try:
                    if not re.fullmatch(r'[A-Z0-9_-]{3,40}',student_id):
                        raise ValueError('Student ID must contain 3–40 letters, numbers, hyphens or underscores.')
                    db.execute('BEGIN IMMEDIATE')
                    student=db.execute('SELECT * FROM students WHERE student_id=?',(student_id,)).fetchone()
                    if action=='create':
                        name=request.form.get('name','').strip()
                        password=request.form.get('password','')
                        if not 1<=len(name)<=100 or not 12<=len(password)<=128:
                            raise ValueError('Enter a name and a password of 12–128 characters.')
                        if student:
                            raise ValueError('That student ID already exists.')
                        db.execute('INSERT INTO students(student_id,name,active,password_hash) VALUES (?,?,1,?)',(student_id,name,generate_password_hash(password)))
                    elif action=='password':
                        password=request.form.get('password','')
                        if not student or not 12<=len(password)<=128:
                            raise ValueError('Select an existing student and a password of 12–128 characters.')
                        db.execute('UPDATE students SET password_hash=? WHERE student_id=?',(generate_password_hash(password),student_id))
                        db.execute('DELETE FROM mobile_sessions WHERE student_id=?',(student_id,))
                        db.execute('DELETE FROM mobile_login_attempts WHERE student_id=?',(student_id,))
                    elif action in ('disable','enable'):
                        if not student:
                            raise ValueError('Student not found.')
                        if action=='disable' and db.execute('SELECT 1 FROM rides WHERE student_id=? AND returned_at IS NULL',(student_id,)).fetchone():
                            raise ValueError('Complete this student’s active ride before disabling their account.')
                        db.execute('UPDATE students SET active=? WHERE student_id=?',(1 if action=='enable' else 0,student_id))
                        db.execute('DELETE FROM mobile_sessions WHERE student_id=?',(student_id,))
                    else:
                        raise ValueError('Unknown action.')
                    db.commit()
                    flash(f'{student_id}: account updated.','success')
                except ValueError as error:
                    db.rollback();flash(str(error),'error')
                return redirect(url_for('admin_accounts'))
            students=db.execute('SELECT student_id,name,active,password_hash IS NOT NULL AS has_password FROM students ORDER BY student_id').fetchall()
        return render_template('admin_accounts.html',students=students)

    @app.route('/admin/export/rides.csv')
    @admin_required
    def export_rides():
        with closing(get_db()) as db:
            rows=db.execute('SELECT ride_id,student_id,bike_id,rented_at,returned_at,start_station,start_slot,return_station,return_slot FROM rides ORDER BY ride_id').fetchall()
        output=io.StringIO(); writer=csv.writer(output)
        writer.writerow(['ride_id','student_id','bike_id','rented_at_IST','returned_at_IST','start_station','start_slot','return_station','return_slot'])
        def safe(value):
            value='' if value is None else str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        writer.writerows([safe(value) for value in row] for row in rows)
        return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=campusbike-rides.csv','Cache-Control':'no-store'})
