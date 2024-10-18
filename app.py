import os
import uuid
from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory, flash
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, TextAreaField, DateTimeLocalField, FieldList, FormField, IntegerField
from wtforms.validators import DataRequired
import pandas as pd
import re
from flask_session import Session
from flask_wtf.file import FileField, FileAllowed
from flask import send_from_directory

app = Flask(__name__)
app.config['SECRET_KEY'] = 'John@123'  # Replace with an actual secret key
app.config['UPLOAD_FOLDER'] = 'uploads'  # Folder to store temporary files
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

# Configure server-side session storage
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions on the server-side filesystem
Session(app)  # Initialize the server-side session

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Country code mapping
country_codes = {
    "Egypt": "EG",
    "United Arab Emirates": "AE",
    "Oman": "OM",
    "Bahrain": "BH",
    "Qatar": "QA",
    "Iraq": "IQ",
    "Jordan": "JO",
    "Kuwait": "KW"
}

# Define the forms
class UploadForm(FlaskForm):
    image = FileField('Upload Image', validators=[FileAllowed(['jpg', 'png'], 'Images only!')])
    submit = SubmitField('Submit')

class VendorDataForm(FlaskForm):
    csv_file = FileField('CSV File', validators=[DataRequired()])
    submit = SubmitField('Upload')

class LogisticsEventForm(FlaskForm):
    webinar_url = StringField('Webinar URL', validators=[DataRequired()])
    date_time = DateTimeLocalField('Webinar Date and Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    notes = TextAreaField('Notes')

class LogisticsForm(FlaskForm):
    events = FieldList(FormField(LogisticsEventForm), min_entries=1)
    submit = SubmitField('Save')

class WhatsAppLinkForm(FlaskForm):
    link_text = StringField('Link Text', validators=[DataRequired()])
    link_url = StringField('Link URL', validators=[DataRequired()])

class WhatsAppMessageForm(FlaskForm):
    message_body = TextAreaField('WhatsApp Message Body', validators=[DataRequired()])
    date_time = DateTimeLocalField('Message Date and Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    links = FieldList(FormField(WhatsAppLinkForm), min_entries=1)
    add_link = SubmitField('Add Link')

class ContentForm(FlaskForm):
    email_content = TextAreaField('Email Content', validators=[DataRequired()])
    email_date_time = DateTimeLocalField('Email Date and Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    whatsapp_messages = FieldList(FormField(WhatsAppMessageForm), min_entries=1)
    image = FileField('Upload Image', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    add_message = SubmitField('Add WhatsApp Message')
    submit = SubmitField('Save')

class EmailReportForm(FlaskForm):
    email_count = IntegerField('Emails Entered', validators=[DataRequired()])
    sent = IntegerField('Emails Sent', validators=[DataRequired()])
    read = IntegerField('Emails Read', validators=[DataRequired()])

class WhatsAppReportForm(FlaskForm):
    dispatched = IntegerField('Dispatched', validators=[DataRequired()])
    sent = IntegerField('Sent', validators=[DataRequired()])
    read = IntegerField('Read', validators=[DataRequired()])
    clicked = IntegerField('Clicked', validators=[DataRequired()])

class ReportingForm(FlaskForm):
    email_report = FormField(EmailReportForm)
    whatsapp_report = FormField(WhatsAppReportForm)
    submit = SubmitField('Generate Report')

# Function to read and process vendor data
def read_vendor_data(file):
    try:
        # Read the CSV file into a DataFrame
        df = pd.read_csv(file)
        print("CSV file read successfully.")  # Debugging print
        df.columns = df.columns.str.strip().str.lower()  # Normalize column names

        # Rename 'mobile number' to 'owner_phone'
        if 'mobile number' in df.columns:
            df.rename(columns={'mobile number': 'owner_phone'}, inplace=True)
        else:
            flash("Missing required column: 'mobile number'")
            return None

        # Rename 'account email' to 'email'
        if 'account email' in df.columns:
            df.rename(columns={'account email': 'email'}, inplace=True)
        else:
            flash("Missing required column: 'account email'")
            return None

        # Create 'external_id' column using 'country code' and 'grid'
        if 'account country' in df.columns and 'grid' in df.columns:
            df['country code'] = df['account country'].map(country_codes)
            df['external_id'] = df['country code'] + '_' + df['grid'].astype(str)
            df.drop(columns=['country code'], inplace=True)
        else:
            flash("Missing required columns: 'account country' and/or 'grid'")
            return None

        # Keep only the necessary columns
        df = df[['external_id', 'email', 'owner_phone']]

        # Validate phone numbers
        invalid_phone_numbers = df[~df['owner_phone'].apply(lambda x: bool(re.match(r'^\+?[1-9]\d{1,14}$', str(x))))]

        if not invalid_phone_numbers.empty:
            flash("The following rows have invalid phone numbers:")
            for index, row in invalid_phone_numbers.iterrows():
                flash(f"Row {index + 1}: {row['owner_phone']}")
        
        # Return the cleaned DataFrame
        return df
    except Exception as e:
        print(f"Error while reading CSV: {e}")  # Debugging print
        flash(f"Error processing data: {e}")
        return None

# Route for the upload form

@app.route('/', methods=['GET', 'POST'])
def index():
    form = UploadForm()
    if form.validate_on_submit():
        if form.image.data:
            image_file = form.image.data
            image_filename = image_file.filename
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)  # Save the uploaded file to the designated folder
            session['image_filename'] = image_filename  # Store the file name in session
        return redirect(url_for('content_view'))
    return render_template('content.html', form=form)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    form = VendorDataForm()
    if request.method == 'POST':
        print("POST request received")  # Debugging print
        if form.validate_on_submit():
            print("Form validated")  # Debugging print
            file = form.csv_file.data
            df = read_vendor_data(file)
            if df is not None:
                filename = str(uuid.uuid4()) + '.csv'
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    df.to_csv(filepath, index=False)
                    print(f"File saved to {filepath}")  # Debugging print
                    session['filename'] = filename
                    session['vendor_data_row_count'] = len(df)
                    flash(f"File uploaded successfully with {len(df)} rows.")
                    return redirect(url_for('dashboard'))
                except Exception as e:
                    print(f"Error saving file: {e}")  # Debugging print
                    flash(f"Error saving file: {e}")
            else:
                flash("Error processing data.")
        else:
            print("Form validation failed")  # Debugging print
            flash("Form validation failed. Please upload a valid CSV file.")
    return render_template('upload.html', form=form)



@app.route('/vendor_data')
def vendor_data():
    # Get the filename from the session
    filename = session.get('filename', None)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename) if filename else None

    # Check if the file exists
    if filepath and os.path.exists(filepath):
        # Load the vendor data
        df = pd.read_csv(filepath)
        row_count = len(df)
        return render_template('vendor_data.html', row_count=row_count)
    else:
        flash("No vendor data available.")
        return redirect(url_for('dashboard'))



# Route for the logistics form
@app.route('/logistics', methods=['GET', 'POST'])
def logistics():
    form = LogisticsForm()
    if form.validate_on_submit():
        logistics_events = []
        for event_form in form.events:
            event = {
                'webinar_url': event_form.webinar_url.data,
                'date_time': event_form.date_time.data.strftime('%Y-%m-%d %H:%M'),
                'notes': event_form.notes.data
            }
            logistics_events.append(event)
        session['logistics_completed'] = True
        session['logistics_events'] = logistics_events
        flash("Logistics information saved successfully.")
        return redirect(url_for('dashboard'))
    return render_template('logistics.html', form=form)

@app.route('/logistics_view', methods=['GET', 'POST'])
def logistics_view():
    # Check if logistics events exist in the session and initialize form accordingly
    if 'logistics_events' in session:
        logistics_events = session.get('logistics_events', [])
        form = LogisticsForm(events=[{} for _ in range(len(logistics_events))])
    else:
        form = LogisticsForm()

    if form.validate_on_submit():
        # If form is submitted and validated, save updated logistics events to session
        logistics_events = []
        for event_form in form.events:
            event = {
                'webinar_url': event_form.webinar_url.data,
                'date_time': event_form.date_time.data.strftime('%Y-%m-%d %H:%M'),
                'notes': event_form.notes.data
            }
            logistics_events.append(event)
        session['logistics_events'] = logistics_events
        flash("Logistics information updated successfully.")
        return redirect(url_for('dashboard'))

    # Populate form fields with existing session data if available
    if 'logistics_events' in session:
        logistics_events = session.get('logistics_events', [])
        for idx, event in enumerate(logistics_events):
            if idx < len(form.events):
                form.events[idx].webinar_url.data = event['webinar_url']
                form.events[idx].date_time.data = pd.to_datetime(event['date_time'], format='%Y-%m-%d %H:%M')
                form.events[idx].notes.data = event['notes']

    return render_template('logistics_view.html', form=form)


@app.route('/content', methods=['GET', 'POST'])
def content():
    form = ContentForm()
    if request.method == 'POST':
        print("POST request received for content")  # Debugging print
        if form.validate_on_submit():
            print("Content form validated")  # Debugging print
            # Handle the image upload
            if form.image.data:
                image_file = form.image.data
                image_filename = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
                image_file.save(image_filename)
                session['image_filename'] = image_filename

            # Save other form data as before
            email_content = form.email_content.data
            whatsapp_messages = []
            for message_form in form.whatsapp_messages:
                message = {
                    'message_body': message_form.message_body.data,
                    'date_time': message_form.date_time.data.strftime('%Y-%m-%d %H:%M'),
                    'links': [{'link_text': link_form.link_text.data, 'link_url': link_form.link_url.data} for link_form in message_form.links]
                }
                whatsapp_messages.append(message)
            session['content_completed'] = True
            session['email_content'] = email_content
            session['email_date_time'] = form.email_date_time.data.strftime('%Y-%m-%d %H:%M')
            session['whatsapp_messages'] = whatsapp_messages
            flash("Content information saved successfully.")
            return redirect(url_for('dashboard'))
        else:
            print("Content form validation failed")  # Debugging print
            for field, errors in form.errors.items():
                for error in errors:
                    print(f"Error in {field}: {error}")  # Debugging print
            flash("Form validation failed. Please check the fields and try again.")

    # Populate form if data already exists in session
    if 'content_completed' in session:
        form.email_content.data = session.get('email_content', '')
        form.email_date_time.data = pd.to_datetime(session.get('email_date_time', ''), format='%Y-%m-%d %H:%M', errors='coerce')
        whatsapp_messages = session.get('whatsapp_messages', [])
        for idx, message in enumerate(whatsapp_messages):
            if idx < len(form.whatsapp_messages):
                form.whatsapp_messages[idx].message_body.data = message['message_body']
                form.whatsapp_messages[idx].date_time.data = pd.to_datetime(message['date_time'], format='%Y-%m-%d %H:%M', errors='coerce')
                for link_idx, link in enumerate(message['links']):
                    if link_idx < len(form.whatsapp_messages[idx].links):
                        form.whatsapp_messages[idx].links[link_idx].link_text.data = link['link_text']
                        form.whatsapp_messages[idx].links[link_idx].link_url.data = link['link_url']

        if 'image_filename' in session:
            form.image.data = session.get('image_filename')

    return render_template('content.html', form=form)


@app.route('/content_view', methods=['GET', 'POST'])
def content_view():
    form = ContentForm()
    # Populate the form with data from the session if available
    if 'content_completed' in session:
        form.email_content.data = session.get('email_content', '')
        form.email_date_time.data = pd.to_datetime(session.get('email_date_time', ''), format='%Y-%m-%d %H:%M', errors='coerce')
        whatsapp_messages = session.get('whatsapp_messages', [])
        for idx, message in enumerate(whatsapp_messages):
            if idx < len(form.whatsapp_messages):
                form.whatsapp_messages[idx].message_body.data = message['message_body']
                form.whatsapp_messages[idx].date_time.data = pd.to_datetime(message['date_time'], format='%Y-%m-%d %H:%M', errors='coerce')
                for link_idx, link in enumerate(message['links']):
                    if link_idx < len(form.whatsapp_messages[idx].links):
                        form.whatsapp_messages[idx].links[link_idx].link_text.data = link['link_text']
                        form.whatsapp_messages[idx].links[link_idx].link_url.data = link['link_url']

    if form.validate_on_submit():
        email_content = form.email_content.data
        whatsapp_messages = []
        for message_form in form.whatsapp_messages:
            message = {
                'message_body': message_form.message_body.data,
                'date_time': message_form.date_time.data.strftime('%Y-%m-%d %H:%M'),
                'links': [{'link_text': link_form.link_text.data, 'link_url': link_form.link_url.data} for link_form in message_form.links]
            }
            whatsapp_messages.append(message)

        # Update session data
        session['email_content'] = email_content
        session['email_date_time'] = form.email_date_time.data.strftime('%Y-%m-%d %H:%M')
        session['whatsapp_messages'] = whatsapp_messages
        flash("Content information updated successfully.")
        return redirect(url_for('dashboard'))

    return render_template('content_view.html', form=form)


# Route for the reporting form
@app.route('/reporting', methods=['GET', 'POST'])
def reporting():
    form = ReportingForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            # Store email report data in session
            email_report = {
                'email_count': form.email_report.email_count.data,
                'sent': form.email_report.sent.data,
                'read': form.email_report.read.data
            }
            # Store WhatsApp report data in session
            whatsapp_report = {
                'dispatched': form.whatsapp_report.dispatched.data,
                'sent': form.whatsapp_report.sent.data,
                'read': form.whatsapp_report.read.data,
                'clicked': form.whatsapp_report.clicked.data
            }
            session['email_report'] = email_report
            session['whatsapp_report'] = whatsapp_report
            flash("Report generated successfully.")
            return redirect(url_for('view_reporting'))
    return render_template('reporting.html', form=form)

# Route for viewing the reporting data
@app.route('/view_reporting', methods=['GET'])
def view_reporting():
    email_report = session.get('email_report', None)
    whatsapp_report = session.get('whatsapp_report', None)
    if email_report is None or whatsapp_report is None:
        flash("No report data available. Please generate a report first.")
        return redirect(url_for('reporting'))
    return render_template('view_reporting.html', email_report=email_report, whatsapp_report=whatsapp_report)

# Route for the dashboard
@app.route('/dashboard')
def dashboard():
    filename = session.get('filename', None)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename) if filename else None
    print(f"Dashboard check - Filepath: {filepath}")  # Debugging print
    file_exists = os.path.exists(filepath) if filepath else False

    logistics_completed = session.get('logistics_completed', False)
    content_completed = session.get('content_completed', False)

    progress = {
        'Vendor Data': 'Uploaded' if file_exists else 'Pending',
        'Logistics': 'Completed' if logistics_completed else 'Pending',
        'Content': 'Completed' if content_completed else 'Pending',
        'Reporting': 'Pending'  # Assuming no specific logic for 'Reporting' yet
    }

    # Pass filename if it exists, so the dashboard can use it
    return render_template('dashboard.html', progress=progress, filename=filename if file_exists else None, row_count=session.get('vendor_data_row_count', 0))

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
