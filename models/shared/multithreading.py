import psycopg2, threading, time
from odoo import models, fields, registry, api, _

class ems_multithreading(models.AbstractModel):   
    _name = 'ems.multithreading'
    _description = 'EMS multithreading model\'s code)'    

    is_running = fields.Boolean(string="Running", default=False)

    # NOTE: This is not an Odoo field, this is used to prevent data replication on retries on multi-threading executions.
	# 		When working with threads, BBDD changes could fail due to concurrent updates. Odoo manages transactions well, 
	# 		so retries can be done, but changes to LimeSurvey must be tracked and repetitions should be avoided. This is 
	# 		for what "changes" is used for. Each LimeSurvey change is tracked in "changes", and its done only if "changes" 
	# 		does not its flag. 
    changes = {}

    # Requests a soft data reload for the current form (updates just the changes, without reloading the window). 
    def reload_request(self, message="Data updated on server side, client reload requested."):  
        # NOTE: for something like a progress bar, cr.commit() is needed. Otherwise, the message is sent on process completion.       
        self.env.user._bus_send("reload_request", {
            "model": self._name,
            "record_id": self.id,
            "message": message
        })

    # The 'func' method will run only once avoiding repetitions. Useful when runnint within a thread with retries (due to BBDD commit's concurrent exception)
    def execute_once(self, func, key=None, *args, **kwargs):
        result = True
        if key is None: key = func.__func__.__name__

        if not self.changes.get(key, False):
            if isinstance(func, str):
                func = getattr(self, func)                
            result = func(*args, **kwargs)                            
            self.changes[key] = True
        return result            

    # Allows running the 'func' method in a new thread with retries (due to BBDD commit's concurrent exception).
    def run_in_thread(self, func, max_retries=5, *args, **kwargs):
        uid = self.env.uid
        dbname = self.env.cr.dbname
        context = dict(self.env.context)
        record_ids = self.ids 
        model_name = self._name
            
        def threaded_worker():			
            self.changes.clear()
            db_registry = registry(dbname)
            # NOTE: I checked that, in some environments and situations, the first run always fails due to concurrent updates.
            #		I'm not sure if waiting a second prior to the first run is faster than the first retry (which waits 0 seconds)...
            for current_try in range(max_retries):
                try:					
                    with db_registry.cursor() as cr:
                        env = api.Environment(cr, uid, context)
                        n_self = env[model_name].browse(record_ids)

                        if isinstance(func, str):
                            method_to_call = getattr(n_self, func)
                            method_to_call(*args, **kwargs)

                        elif callable(func):
                            func(n_self, *args, **kwargs)

                        break

                except psycopg2.errors.SerializationFailure:
                    if current_try == max_retries: raise
                    time.sleep(current_try)
        
        thread = threading.Thread(target=threaded_worker)
        thread.start()
        return thread
    
    # Useful to abort executions if the current entry is already running, also notifies.
    def already_running(self):
        if self.is_running:
            self.notify(_("LimeSurvey: already running"), _("Process already running, maybe by another user?"), "danger")		
        return self.is_running