from flask import Flask, request, jsonify, Response
import sqlite3
import subprocess 

## app.js defined constants and variables here with require? 
# require() in nodejs -> loads modules, same as python import 

app = Flask(__name__)

## CONNECT TO MQTT? 
# var client  = mqtt.connect('mqtt://localhost:1883')
# const LOG_TOPIC = `pioreactor/${os.hostname()}/$experiment/logs/ui`


## UTILS

def dict_factory(cursor, row):
    col_names = [col[0] for col in cursor.description]
    return {key: value for key, value in zip(col_names, row)}

def get_db_connection():
    if app.debug:
        conn = sqlite3.connect('test.sqlite')
    else:
        conn = sqlite3.connect('/home/pioreactor/.pioreactor/storage/pioreactor.sqlite')
    conn.row_factory = dict_factory
    return conn


## ROUTES


@app.route('/', methods = ['GET'])
def redirect_to_overview():
    """Redirects to overview page."""
    return redirect("/overview", code=301)
    
@app.route('/overview', methods = ['GET'])
def overview():
    '''Displays experiment information'''
    return 
    
@app.route('/export-data', methods = ['GET'])
def export_data():
    '''Access old experiment data, available for export'''
    return render_template('index.html')
    
@app.route('/start-new-experiment', methods = ['GET'])
def start_new_experiment():
    '''Create a new experiment.'''
    return 
    
@app.route('/plugins', methods = ['GET'])
def plugins():
    '''Shows list of community plugins, available for installation.'''
    return 
    
@app.route('/analysis', methods = ['GET'])
def analysis():
    '''Displays data of previous experiments.'''
    return 
    
@app.route('/feedback', methods = ['GET'])
def feedback():
    '''Submit feedback.'''
    if request.method == "POST":
        body = request.get_json()
        
        # 1. check if all required fields are filled (email, what went wrong)
        
        # 2. are we posting to database or just sending an email lol 
        
    return 
    
@app.route('/config', methods = ['GET'])
def config():
    return 
    
@app.route('/pioreactors', methods = ['GET'])
def pioreactors():
    return 


## not active


@app.route('/pioreactors/<unit>', methods = ['GET'])
def pioreactors_unit():
    return 
    
@app.route('/updates', methods = ['GET'])
def updates():
    return 
    
@app.route('/calibrations', methods = ['GET'])
def calibrations():
    return 
    
## PIOREACTOR CONTROL

@app.route('/stop-all', methods = ['POST'])
def stop_all():
    '''Kills all jobs'''
    result = subprocess.run(["pios", "kill", "--all-jobs", "-y"], capture_output=True)
    
    if result.returncode == 0: 
        return Response(200)
    
    else: 
        print(result.stdout) 
        print(result.stderr) 
        return Response(500)
    
@app.route('/stop/<job>/<unit>', methods = ['POST'])
def stop_job_on_unit(job, unit):
    '''Kills specified job on unit'''
    result = subprocess.run(["pios", "kill", job, "-y", "--units", unit], capture_output=True)
    
    if result.returncode == 0: 
        return Response(200)
    
    else: 
        print(result.stdout) 
        print(result.stderr) 
        return Response(500)

@app.route('/run/<job>/<unit>', methods = ['POST'])
def run_job_on_unit():
    '''Runs specified job on unit'''
    result = subprocess.run(["pios", "run", job, "-y", "--units", unit], capture_output=True)
    
    if result.returncode == 0: 
        return Response(200)
    
    else: 
        print(result.stdout) 
        print(result.stderr) 
        return Response(500) 
    
@app.route('/reboot/<unit>', methods = ['POST'])
def reboot_unit(unit):
    '''Reboots unit''' #should return a 0 
    result = subprocess.run(["pios", "reboot", "-y", "--units", unit], capture_output=True)
    
    if result.returncode == 0:
        return Response(200)
    
    #log an error, figure out later
    else: 
        print(result.stdout) #normal outputs 
        print(result.stderr) #errors 
        return Response(500)

    
## DATA FOR CARDS ON OVERVIEW 


@app.route('/recent_logs', methods = ['GET'])
def recent_logs():
    '''Shows event logs from all units'''
    args = request.args
    if "min_level" in args: 
        min_level = args["min_level"]
    else:
        min_level = "INFO"
        
    if min_level == "DEBUG":
        level_string = '(level == "ERROR" or level == "WARNING" or level == "NOTICE" or level == "INFO" or level == "DEBUG")'
    elif (min_level == "INFO"):
        level_string = '(level == "ERROR" or level == "NOTICE" or level == "INFO" or level == "WARNING")'
    elif (min_level == "WARNING"):
        level_string = '(level == "ERROR" or level == "WARNING")'
    elif (min_level == "ERROR"):
        level_string = '(level == "ERROR")'
    else:
        level_string = '(level == "ERROR" or level == "NOTICE" or level == "INFO" or level == "WARNING")'
        
    conn = get_db_connection()
    
    recent_logs = conn.execute(f"SELECT l.timestamp, level=='ERROR'as is_error, level=='WARNING' as is_warning, level=='NOTICE' as is_notice, l.pioreactor_unit, message, task FROM logs AS l LEFT JOIN latest_experiment AS le ON (le.experiment = l.experiment OR l.experiment=?) WHERE {level_string} AND l.timestamp >= MAX(strftime('%Y-%m-%dT%H:%M:%S', datetime('now', '-24 hours')), le.created_at) ORDER BY l.timestamp DESC LIMIT 50;", ("'$experiment'",)).fetchall()
    
    return jsonify(recent_logs)
    
@app.route('/time_series/growth_rates/<experiment>', methods = ['GET'])
def growth_rates(experiment):
    '''Gets growth rates for all units'''
    args = request.args
    filter_mod_n = args.get("filter_mod_n", 100)
    
    conn = get_db_connection()
    
    growth_rates = conn.execute("SELECT json_object('series', json_group_array(unit), 'data', json_group_array(json(data))) as result FROM (SELECT pioreactor_unit as unit, json_group_array(json_object('x', timestamp, 'y', round(rate, 5))) as data FROM growth_rates WHERE experiment=? AND ((ROWID * 0.61803398875) - cast(ROWID * 0.61803398875 as int) < 1.0/?) GROUP BY 1);", (experiment, filter_mod_n)).fetchone()

    return growth_rates['result']
    
@app.route('/time_series/temperature_readings/<experiment>', methods = ['GET'])
def temperature_readings(experiment):
    '''Gets temperature readings for all units'''
    args = request.args
    filter_mod_n = args.get("filter_mod_n", 100)
    
    conn = get_db_connection()
    
    temperature_readings = conn.execute("SELECT json_object('series', json_group_array(unit), 'data', json_group_array(json(data))) as result FROM (SELECT pioreactor_unit as unit, json_group_array(json_object('x', timestamp, 'y', round(temperature_c, 2))) as data FROM temperature_readings WHERE experiment=? AND ((ROWID * 0.61803398875) - cast(ROWID * 0.61803398875 as int) < 1.0/?) GROUP BY 1);", (experiment, filter_mod_n)).fetchone()

    return temperature_readings['result']
    
@app.route('/time_series/od_readings_filtered/<experiment>', methods = ['GET'])
def od_readings_filtered(experiment):
    '''Gets normalized od for all units'''
    args = request.args
    filter_mod_n = args.get("filter_mod_n", 100)
    lookback = float(args.get("lookback", 4))
    
    conn = get_db_connection()
    
    filtered_od_readings = conn.execute(f"SELECT json_object('series', json_group_array(unit), 'data', json_group_array(json(data))) as result FROM (SELECT pioreactor_unit as unit, json_group_array(json_object('x', timestamp, 'y', round(normalized_od_reading, 7))) as data FROM od_readings_filtered WHERE experiment=? AND ((ROWID * 0.61803398875) - cast(ROWID * 0.61803398875 as int) < 1.0/?) AND timestamp > strftime('%Y-%m-%dT%H:%M:%S', datetime('now',?)) GROUP BY 1);", (experiment, filter_mod_n, f"-{lookback} hours")).fetchone()
    return filtered_od_readings['result']
    
@app.route('/time_series/od_readings/<experiment>', methods = ['GET'])
def od_readings(experiment):
    '''Gets raw od for all units'''
    args = request.args
    filter_mod_n = args.get("filter_mod_n", 100)
    lookback = float(args.get("lookback", 4)) 
    
    conn = get_db_connection()
    
    raw_od_readings = conn.execute("SELECT json_object('series', json_group_array(unit), 'data', json_group_array(json(data))) as result FROM (SELECT pioreactor_unit || '-' || channel as unit, json_group_array(json_object('x', timestamp, 'y', round(od_reading, 7))) as data FROM od_readings WHERE experiment=? AND ((ROWID * 0.61803398875) - cast(ROWID * 0.61803398875 as int) < 1.0/?) and timestamp > strftime('%Y-%m-%dT%H:%M:%S', datetime('now', ?)) GROUP BY 1);", (experiment, filter_mod_n, f"-{lookback} hours")).fetchone()

    return raw_od_readings['result']
    
@app.route('/time_series/alt_media_fraction/<experiment>', methods = ['GET'])
def alt_media_fraction(experiment):
    '''unsure...'''
    
    conn = get_db_connection()
    
    alt_media_fraction_ = conn.execute("SELECT json_object('series', json_group_array(unit), 'data', json_group_array(json(data))) as result FROM (SELECT pioreactor_unit as unit, json_group_array(json_object('x', timestamp, 'y', round(alt_media_fraction, 7))) as data FROM alt_media_fractions WHERE experiment=? GROUP BY 1);", (experiment,)).fetchone()

    return alt_media_fraction_['result']
    
@app.route('/recent_media_rates', methods = ['GET'])
def recent_media_rates():
    '''Shows amount of added media per unit'''
    ## this one confusing 
    hours = 3 
    
    conn = get_db_connection()
    
    recent_media_rate = conn.execute("SELECT d.pioreactor_unit, SUM(CASE WHEN event='add_media' THEN volume_change_ml ELSE 0 END) / ? AS media_rate, SUM(CASE WHEN event='add_alt_media' THEN volume_change_ml ELSE 0 END) / ? AS alt_media_rate FROM dosing_events AS d JOIN latest_experiment USING (experiment) WHERE datetime(d.timestamp) >= datetime('now', '-? Hour') AND event IN ('add_alt_media', 'add_media') AND source_of_event LIKE 'dosing_automation%' GROUP BY d.pioreactor_unit;", (hours, hours)).fetchone()
    
    return recent_media_rate['alt_media_rate']


## CALIBRATIONS


@app.route('/calibrations/<pioreactor_unit>/<calibration_type>', methods = ['GET'])
def get_unit_calibrations(pioreactor_unit, calibration_type):
    
    conn = get_db_connection()
    
    unit_calibration = conn.execute("SELECT * FROM calibrations WHERE type=? AND pioreactor_unit=?", (calibration_type, pioreactor_unit)).fetchall()
    return jsonify(unit_calibration)
   
   
## PLUGINS


@app.route('/get_installed_plugins', methods = ['GET'])
def list_installed_plugins():
    result = subprocess.run(["pio", "list-plugins", "--json"], capture_output=True)
    
    if result.returncode == 0: 
        return Response(200)
    
    else: 
        print(result.stdout) 
        print(result.stderr) 
        return Response(500)
    
@app.route('/install_plugins', methods = ['POST'])
def install_plugin():
    result = subprocess.run(["pios", "install-plugin"], capture_output=True)
    
    if result.returncode == 0: 
        return Response(200)
    
    else: 
        print(result.stdout) 
        print(result.stderr) 
        return Response(500)
    
@app.route('/uninstall_plugins', methods = ['POST'])
def uninstall_plugin():
    result = subprocess.run(["pios", "uninstall-plugin"], capture_output=True)
    
    if result.returncode == 0: 
        return Response(200)
    
    else: 
        print(result.stdout) 
        print(result.stderr) 
        return Response(500)
    

## MISC 


@app.route('/contrib/automations/<type>', methods = ['GET'])
def something_():
    return
    
@app.route('/contrib/jobs', methods = ['GET'])
def something__():
    return
    
@app.route('/update_app', methods = ['POST'])
def update_app():
    return
    
@app.route('/get_app_version', methods = ['GET'])
def get_app_version():
    return
    
@app.route('/export_datasets', methods = ['POST'])
def export_datasets():
    return

@app.route('/get_experiments', methods = ['GET'])
def get_experiments():
    conn = get_db_connection()
    experiments = conn.execute('SELECT experiment, created_at, description FROM experiments ORDER BY created_at DESC;').fetchall()
    return jsonify(experiments)
    
@app.route('/get_latest_experiment', methods = ['GET'])
def get_latest_experiment():
    conn = get_db_connection()
    latest_experiment = conn.execute('SELECT experiment, created_at, description, media_used, organism_used, delta_hours FROM latest_experiment').fetchone()
    return jsonify(latest_experiment)
    
@app.route('/get_current_unit_labels', methods = ['GET'])
def get_current_unit_labels():
    return
    
@app.route('/update_current_unit_labels', methods = ['POST'])
def update_current_unit_labels():
    return
    
@app.route('/get_historical_organisms_used', methods = ['GET'])
def get_historical_organisms_used():
    conn = get_db_connection()
    historical_organisms = conn.execute('SELECT DISTINCT organism_used as key FROM experiments WHERE NOT (organism_used IS NULL OR organism_used == "") ORDER BY created_at DESC;').fetchall()
    return jsonify(historical_organisms)
    
@app.route('/get_historical_media_used', methods = ['GET'])
def get_historical_media_used():
    conn = get_db_connection()
    historical_media = conn.execute('SELECT DISTINCT media_used as key FROM experiments WHERE NOT (media_used IS NULL OR media_used == "") ORDER BY created_at DESC;').fetchall()
    return jsonify(historical_media)
    
@app.route('/create_experiment', methods = ['POST'])
def create_experiment():
    
    body = request.get_json()
    
    conn = get_db_connection()
    try: 
        conn.execute('INSERT INTO experiments (created_at, experiment, description, media_used, organism_used) VALUES (?,?,?,?,?)', (body['created_at'], body['experiment'], body['description'], body['media_used'], body['organism_used']))
        return Response(200)
    
    except sqlite3.IntegrityError: 
        #publish to mqtt
        return Response(400)
        
    
@app.route('/update_experiment_desc', methods = ['POST'])
def update_experiment_description():
    return
    
@app.route('/add_new_pioreactor', methods = ['POST'])
def add_new_pioreactor():
    return
    

## CONFIG CONTROL


@app.route('/get_config/<filename>', methods = ['GET'])
def get_config_of_file():
    return
    
@app.route('/get_configs', methods = ['GET'])
def get_list_all_configs():
    return
    
@app.route('/delete_config', methods = ['POST'])
def delete_config():
    return
    
@app.route('/save_new_config', methods = ['POST'])
def save_new_config():
    return
    
    
## START SERVER

