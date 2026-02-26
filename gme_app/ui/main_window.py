"""Main application window."""

from __future__ import annotations 

import json 
from datetime import datetime 
from pathlib import Path 
from typing import Any 

from PyQt6 .QtCore import QThreadPool 
from PyQt6 .QtWidgets import QMainWindow ,QStackedWidget 

from gme_app .api .client import ApiError ,GMEManagementClient 
from gme_app .config import AppConfig 
from gme_app .models import Artifact ,AudioProvider ,ProcessingRun ,Project ,UserProfile 
from gme_app .services .session_store import SessionStore 
from gme_app .ui .admin_view import AdminView 
from gme_app .ui .auth_view import AuthView 
from gme_app .ui .dashboard_view import DashboardView 
from gme_app .ui .profile_view import ProfileView 
from gme_app .ui .project_view import ProjectView ,safe_float 
from gme_app .workers import Worker 

LIE_RISK_KEYS :tuple [str ,...]=(
"risk",
"deception_score",
"deception",
"lie_probability",
"lie_score",
"lie",
)


class MainWindow (QMainWindow ):
    def __init__ (self ,config :AppConfig ,parent =None )->None :
        super ().__init__ (parent )
        self .config =config 
        self .client =GMEManagementClient (
        base_url =config .api_base_url ,
        video_service_base_url =config .video_service_base_url ,
        audio_service_base_url =config .audio_service_base_url ,
        audio_service_api_key =config .audio_service_api_key ,
        timeout_seconds =config .timeout_seconds ,
        session_cookie_name =config .session_cookie_name ,
        )
        self .session_store =SessionStore (config .app_data_dir /"session.json")
        self .thread_pool =QThreadPool .globalInstance ()
        self ._active_workers :set [Worker ]=set ()
        self .current_user :UserProfile |None =None 
        self .current_project_id :str |None =None 
        self .current_project_run_id :str |None =None 
        self ._available_models :list [str ]=[]
        self ._available_detectors :list [str ]=["haar","mtcnn","retinaface","scrfd"]
        self ._available_audio_providers :list [AudioProvider ]=[]
        self ._admin_users_query :str =""
        self ._admin_users_role :str |None =None 
        self ._admin_users_active :bool |None =None 
        self ._admin_projects_query :str =""

        self .setWindowTitle ("GME App")
        self .setMinimumSize (980 ,680 )
        self ._build_ui ()
        self ._connect_signals ()
        self ._restore_session ()

    def _build_ui (self )->None :
        self .stack =QStackedWidget ()
        self .auth_view =AuthView ()
        self .dashboard_view =DashboardView ()
        self .profile_view =ProfileView ()
        self .admin_view =AdminView ()
        self .project_view =ProjectView ()
        self .dashboard_view .set_camera_output_dir (self .config .app_data_dir /"captures")
        self .stack .addWidget (self .auth_view )
        self .stack .addWidget (self .dashboard_view )
        self .stack .addWidget (self .profile_view )
        self .stack .addWidget (self .admin_view )
        self .stack .addWidget (self .project_view )
        self .setCentralWidget (self .stack )
        self .stack .setCurrentWidget (self .auth_view )

    def _connect_signals (self )->None :
        self .auth_view .login_submitted .connect (self ._on_login_submitted )
        self .auth_view .register_submitted .connect (self ._on_register_submitted )

        self .dashboard_view .refresh_requested .connect (self .refresh_dashboard )
        self .dashboard_view .create_project_requested .connect (self ._on_create_project )
        self .dashboard_view .open_project_requested .connect (self ._on_open_project_requested )
        self .dashboard_view .open_profile_requested .connect (self ._show_profile )
        self .dashboard_view .open_admin_requested .connect (self ._show_admin )
        self .dashboard_view .logout_requested .connect (self ._on_logout )

        self .profile_view .back_to_projects_requested .connect (self ._show_dashboard )
        self .profile_view .open_admin_requested .connect (self ._show_admin )
        self .profile_view .save_profile_requested .connect (self ._on_profile_save_requested )
        self .profile_view .change_password_requested .connect (self ._on_change_password_requested )

        self .admin_view .back_to_projects_requested .connect (self ._show_dashboard )
        self .admin_view .open_profile_requested .connect (self ._show_profile )
        self .admin_view .users_filter_requested .connect (self ._on_admin_users_filter_requested )
        self .admin_view .projects_filter_requested .connect (self ._on_admin_projects_filter_requested )
        self .admin_view .change_user_role_requested .connect (self ._on_admin_change_user_role_requested )
        self .admin_view .change_user_active_requested .connect (self ._on_admin_change_user_active_requested )
        self .admin_view .open_project_requested .connect (self ._on_open_project_requested )
        self .admin_view .delete_project_requested .connect (self ._on_admin_delete_project_requested )

        self .project_view .back_requested .connect (self ._on_project_back_requested )
        self .project_view .refresh_requested .connect (self ._on_project_refresh_requested )
        self .project_view .run_selected .connect (self ._on_project_run_selected )
        self .project_view .start_processing_requested .connect (self ._on_start_processing )
        self .project_view .cancel_processing_requested .connect (self ._on_cancel_processing )
        self .project_view .delete_project_requested .connect (self ._on_delete_project )
        self .project_view .add_member_requested .connect (self ._on_add_member_requested )
        self .project_view .change_member_role_requested .connect (self ._on_change_member_role_requested )
        self .project_view .remove_member_requested .connect (self ._on_remove_member_requested )

    def _run_background (
    self ,
    fn ,
    *,
    on_result =None ,
    on_error =None ,
    on_finished =None ,
    )->None :
        worker =Worker (fn )
        self ._active_workers .add (worker )
        if on_result is not None :
            worker .signals .result .connect (on_result )
        if on_error is not None :
            worker .signals .error .connect (on_error )

        def _finalize ()->None :
            self ._active_workers .discard (worker )
            if on_finished is not None :
                on_finished ()

        worker .signals .finished .connect (_finalize )
        self .thread_pool .start (worker )

    def _restore_session (self )->None :
        persisted =self .session_store .load ()
        if not persisted :
            return 
        if persisted .api_base_url !=self .config .api_base_url :
            self .session_store .clear ()
            return 

        self .auth_view .prefill_login (persisted .user_login )
        self .auth_view .set_busy (True ,"Restoring session...")
        self .client .set_session_token (persisted .session_token )

        def task ()->UserProfile :
            return self .client .get_me ()

        def on_success (user :UserProfile )->None :
            self .auth_view .set_busy (False )
            self ._enter_dashboard (user =user ,remember =True ,login_hint =persisted .user_login )

        def on_error (error :Exception )->None :
            self .session_store .clear ()
            self .client .clear_session_token ()
            self .auth_view .set_busy (False )
            self .auth_view .show_info ("Saved session expired. Please sign in again.")
            self ._show_auth ()

        self ._run_background (task ,on_result =on_success ,on_error =on_error )

    def _show_auth (self )->None :
        self .stack .setCurrentWidget (self .auth_view )

    def _show_dashboard (self )->None :
        self .dashboard_view .set_active_nav ("projects")
        self .stack .setCurrentWidget (self .dashboard_view )

    def _show_profile (self )->None :
        if self .current_user is None :
            self ._show_auth ()
            return 
        self .dashboard_view .set_active_nav ("profile")
        self .profile_view .set_admin_mode (self .current_user .role =="admin")
        self .profile_view .set_user (self .current_user )
        self .stack .setCurrentWidget (self .profile_view )

    def _show_admin (self )->None :
        if self .current_user is None :
            self ._show_auth ()
            return 
        if self .current_user .role !="admin":
            self .dashboard_view .set_status_message ("Admin access is required.",is_error =True )
            self ._show_dashboard ()
            return 
        self .dashboard_view .set_active_nav ("admin")
        self .stack .setCurrentWidget (self .admin_view )
        self .refresh_admin_panel ()

    def _show_project (self )->None :
        self .stack .setCurrentWidget (self .project_view )

    def _on_login_submitted (self ,login :str ,password :str ,remember :bool )->None :
        self .auth_view .set_busy (True ,"Signing in...")

        def task ()->dict [str ,Any ]:
            self .client .login (login =login ,password =password )
            user =self .client .get_me ()
            return {"user":user ,"remember":remember ,"login":login }

        def on_success (result :dict [str ,Any ])->None :
            self ._enter_dashboard (
            user =result ["user"],
            remember =bool (result ["remember"]),
            login_hint =str (result ["login"]),
            )

        def on_error (error :Exception )->None :
            self .auth_view .show_login_error (self ._format_error (error ))

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .auth_view .set_busy (False ),
        )

    def _on_register_submitted (self ,login :str ,email :str ,password :str )->None :
        self .auth_view .set_busy (True ,"Creating account...")

        def task ()->dict [str ,Any ]:
            self .client .register (login =login ,password =password ,email =email or None )
            self .client .login (login =login ,password =password )
            user =self .client .get_me ()
            return {"user":user ,"login":login }

        def on_success (result :dict [str ,Any ])->None :
            self ._enter_dashboard (user =result ["user"],remember =True ,login_hint =str (result ["login"]))

        def on_error (error :Exception )->None :
            self .auth_view .show_register_error (self ._format_error (error ))

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .auth_view .set_busy (False ),
        )

    def _enter_dashboard (self ,*,user :UserProfile ,remember :bool ,login_hint :str )->None :
        self .current_user =user 
        self .dashboard_view .set_user (user )
        self .dashboard_view .set_admin_mode (user .role =="admin")
        self .profile_view .set_user (user )
        self .profile_view .set_admin_mode (user .role =="admin")
        self .project_view .set_user (user )
        session_token =self .client .get_session_token ()
        if remember and session_token :
            self .session_store .save (
            api_base_url =self .config .api_base_url ,
            session_token =session_token ,
            user_login =login_hint ,
            )
        else :
            self .session_store .clear ()

        self ._show_dashboard ()
        self .refresh_dashboard ()

    def refresh_dashboard (self )->None :
        if self .current_user is None :
            return 
        self .dashboard_view .set_loading (True ,"Refreshing dashboard...")

        def task ()->dict [str ,Any ]:
            models :list [str ]=[]
            detectors :list [str ]=[]
            audio_providers :list [AudioProvider ]=[]
            audio_providers_error :str |None =None 
            try :
                models =self .client .get_processing_models ()
            except ApiError :
                models =[]
            try :
                detectors =self .client .get_face_detectors ()
            except ApiError :
                detectors =[]
            try :
                audio_providers =self .client .get_audio_providers ()
            except ApiError as exc :
                audio_providers =[]
                audio_providers_error =exc .message 

            projects_page =self .client .list_projects (limit =100 ,offset =0 )
            projects =projects_page .items 
            runs :list [tuple [Project ,ProcessingRun |None ]]=[]

            fetch_runs_limit =min (30 ,len (projects ))
            for index ,project in enumerate (projects ):
                latest_run :ProcessingRun |None =None 
                if index <fetch_runs_limit :
                    try :
                        run_page =self .client .list_processing_runs (
                        project_id =str (project .id ),
                        limit =1 ,
                        offset =0 ,
                        )
                    except ApiError :
                        latest_run =None 
                    else :
                        latest_run =run_page .items [0 ]if run_page .items else None 
                        if latest_run is not None and latest_run .status in {"scheduled","pending","running"}:
                            try :
                                self .client .sync_processing_run (
                                project_id =str (project .id ),
                                run_id =str (latest_run .id ),
                                )
                                run_page =self .client .list_processing_runs (
                                project_id =str (project .id ),
                                limit =1 ,
                                offset =0 ,
                                )
                                latest_run =run_page .items [0 ]if run_page .items else latest_run 
                            except ApiError :
                                pass 
                runs .append ((project ,latest_run ))

            return {
            "models":models ,
            "detectors":detectors ,
            "audio_providers":audio_providers ,
            "audio_providers_error":audio_providers_error ,
            "projects":projects ,
            "runs":runs ,
            }

        def on_success (result :dict [str ,Any ])->None :
            fetched_models =[str (item )for item in result .get ("models",[])if str (item ).strip ()]
            if fetched_models :
                self ._available_models =fetched_models 
            fetched_detectors =[str (item )for item in result .get ("detectors",[])if str (item ).strip ()]
            if fetched_detectors :
                self ._available_detectors =fetched_detectors 
            fetched_audio_providers =[
            item for item in result .get ("audio_providers",[])if isinstance (item ,AudioProvider )and item .code 
            ]
            if fetched_audio_providers :
                self ._available_audio_providers =fetched_audio_providers 

            self .dashboard_view .set_models (self ._available_models )
            self .dashboard_view .set_detectors (self ._available_detectors )
            self .dashboard_view .set_audio_providers (self ._available_audio_providers )
            self .project_view .set_models (self ._available_models )
            self .project_view .set_detectors (self ._available_detectors )
            self .project_view .set_audio_providers (self ._available_audio_providers )
            self .dashboard_view .set_dashboard_data (
            projects =list (result ["projects"]),
            runs =list (result ["runs"]),
            )
            self .dashboard_view .set_status_message (
            f"Data refreshed: {datetime .now ().strftime ('%H:%M:%S')}",
            is_error =False ,
            )
            if result .get ("audio_providers_error"):
                self .dashboard_view .set_status_message (
                f"Audio providers failed to load: {result ['audio_providers_error']}",
                is_error =True ,
                )

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .dashboard_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .dashboard_view .set_loading (False ),
        )

    def refresh_admin_panel (self )->None :
        if self .current_user is None :
            return 
        if self .current_user .role !="admin":
            self .admin_view .set_status_message ("Admin access is required.",is_error =True )
            return 

        self .admin_view .set_loading (True ,"Loading admin data...")

        def task ()->dict [str ,Any ]:
            users_page =self .client .admin_list_users (
            q =self ._admin_users_query or None ,
            role =self ._admin_users_role ,
            is_active =self ._admin_users_active ,
            limit =200 ,
            offset =0 ,
            )
            projects_page =self .client .list_projects (
            q =self ._admin_projects_query or None ,
            limit =200 ,
            offset =0 ,
            )
            return {
            "users":users_page .items ,
            "projects":projects_page .items ,
            }

        def on_success (result :dict [str ,Any ])->None :
            self .admin_view .set_users (list (result .get ("users",[])))
            self .admin_view .set_projects (list (result .get ("projects",[])))
            self .admin_view .set_status_message (
            f"Admin data refreshed: {datetime .now ().strftime ('%H:%M:%S')}",
            is_error =False ,
            )

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .admin_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .admin_view .set_loading (False ),
        )

    def _on_profile_save_requested (self ,email :object ,display_name :object )->None :
        self .profile_view .set_loading (True ,"Saving profile...")

        def task ()->UserProfile :
            return self .client .update_me (
            email =str (email ).strip ()if isinstance (email ,str )else None ,
            display_name =str (display_name ).strip ()if isinstance (display_name ,str )else None ,
            )

        def on_success (user :UserProfile )->None :
            self .current_user =user 
            self .dashboard_view .set_user (user )
            self .profile_view .set_user (user )
            self .project_view .set_user (user )
            self .profile_view .set_status_message ("Profile updated.",is_error =False )

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .profile_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .profile_view .set_loading (False ),
        )

    def _on_change_password_requested (self ,old_password :str ,new_password :str ,revoke_other :bool )->None :
        self .profile_view .set_loading (True ,"Changing password...")

        def task ()->None :
            self .client .change_my_password (
            old_password =old_password ,
            new_password =new_password ,
            revoke_other_sessions =revoke_other ,
            )

        def on_success (_ :Any )->None :
            self .profile_view .clear_password_inputs ()
            self .profile_view .set_status_message ("Password updated.",is_error =False )

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .profile_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .profile_view .set_loading (False ),
        )

    def _on_admin_users_filter_requested (self ,query :str ,role :object ,active :object )->None :
        self ._admin_users_query =query .strip ()
        self ._admin_users_role =str (role ).strip ()if isinstance (role ,str )and str (role ).strip ()else None 
        self ._admin_users_active =active if isinstance (active ,bool )else None 
        self .refresh_admin_panel ()

    def _on_admin_projects_filter_requested (self ,query :str )->None :
        self ._admin_projects_query =query .strip ()
        self .refresh_admin_panel ()

    def _on_admin_change_user_role_requested (self ,user_id :str ,role :str )->None :
        self .admin_view .set_loading (True ,"Updating user role...")

        def task ()->UserProfile :
            return self .client .admin_patch_user_role (user_id =user_id ,role =role )

        def on_success (_ :UserProfile )->None :
            self .admin_view .set_status_message ("User role updated.",is_error =False )
            self .refresh_admin_panel ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .admin_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .admin_view .set_loading (False ),
        )

    def _on_admin_change_user_active_requested (self ,user_id :str ,is_active :bool )->None :
        self .admin_view .set_loading (True ,"Updating user status...")

        def task ()->UserProfile :
            return self .client .admin_patch_user_active (user_id =user_id ,is_active =is_active )

        def on_success (_ :UserProfile )->None :
            message ="User unbanned."if is_active else "User banned."
            self .admin_view .set_status_message (message ,is_error =False )
            self .refresh_admin_panel ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .admin_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .admin_view .set_loading (False ),
        )

    def _on_admin_delete_project_requested (self ,project_id :str )->None :
        self .admin_view .set_loading (True ,"Deleting project...")

        def task ()->None :
            self .client .delete_project (project_id =project_id )

        def on_success (_ :Any )->None :
            self .admin_view .set_status_message ("Project deleted.",is_error =False )
            self .refresh_admin_panel ()
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .admin_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .admin_view .set_loading (False ),
        )

    def _on_create_project (
    self ,
    title :str ,
    description :str ,
    video_path :str ,
    start_processing :bool ,
    model_name :str ,
    detector_name :str ,
    processing_mode :str ,
    audio_provider :str ,
    )->None :
        self .dashboard_view .set_loading (True ,"Creating project...")

        def task ()->dict [str ,Any ]:
            payload =self .client .create_project (
            title =title ,
            description =description or None ,
            video_path =Path (video_path ),
            start_processing =start_processing ,
            model_name =model_name ,
            detector_name =detector_name or None ,
            processing_mode =processing_mode ,
            audio_provider =audio_provider or None ,
            )
            return {"payload":payload }

        def on_success (result :dict [str ,Any ])->None :
            self .dashboard_view .set_status_message ("Project created.",is_error =False )
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .dashboard_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .dashboard_view .set_loading (False ),
        )

    def _on_start_processing (
    self ,
    project_id :str ,
    model_name :str ,
    detector_name :str ,
    processing_mode :str ,
    audio_provider :str ,
    )->None :
        self .project_view .set_loading (True ,"Starting processing...")

        def task ()->dict [str ,Any ]:
            return self .client .start_processing (
            project_id =project_id ,
            model_name =model_name ,
            detector_name =detector_name or None ,
            processing_mode =processing_mode ,
            audio_provider =audio_provider or None ,
            )

        def on_success (_ :dict [str ,Any ])->None :
            self .project_view .set_status_message ("Processing started.",is_error =False )
            self .current_project_run_id =None 
            self ._refresh_project (project_id =project_id ,preferred_run_id ="")
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False ),
        )

    def _on_cancel_processing (self ,project_id :str ,run_id :str )->None :
        self .project_view .set_loading (True ,"Cancelling processing...")

        def task ()->dict [str ,Any ]:
            return self .client .cancel_processing_run (project_id =project_id ,run_id =run_id )

        def on_success (_ :dict [str ,Any ])->None :
            self .project_view .set_status_message ("Processing run cancelled.",is_error =False )
            self .current_project_run_id =run_id 
            self ._refresh_project (project_id =project_id ,preferred_run_id =run_id )
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False ),
        )

    def _on_delete_project (self ,project_id :str )->None :
        self .project_view .set_loading (True ,"Deleting project...")

        def task ()->None :
            self .client .delete_project (project_id =project_id )

        def on_success (_ :Any )->None :
            self .current_project_id =None 
            self .current_project_run_id =None 
            self ._show_dashboard ()
            self .dashboard_view .set_status_message ("Project deleted.",is_error =False )
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False ),
        )

    def _on_logout (self )->None :
        self .dashboard_view .set_loading (True ,"Logging out...")
        self .profile_view .set_loading (True ,"Logging out...")
        self .admin_view .set_loading (True ,"Logging out...")
        self .project_view .set_loading (True ,"Logging out...")

        def task ()->None :
            try :
                self .client .logout ()
            except ApiError as exc :
                if exc .status_code not in (401 ,403 ):
                    raise 

        def on_success (_ :Any )->None :
            self ._reset_session ()
            self .auth_view .show_info ("You have been logged out.")
            self ._show_auth ()

        def on_error (error :Exception )->None :
            message =self ._format_error (error )
            self .dashboard_view .set_status_message (message ,is_error =True )
            self .profile_view .set_status_message (message ,is_error =True )
            self .admin_view .set_status_message (message ,is_error =True )
            self .project_view .set_status_message (message ,is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :(
        self .dashboard_view .set_loading (False ),
        self .profile_view .set_loading (False ),
        self .admin_view .set_loading (False ),
        self .project_view .set_loading (False ),
        ),
        )

    def _on_open_project_requested (self ,project_id :str )->None :
        self .current_project_id =project_id 
        self .current_project_run_id =None 
        if self .current_user is not None :
            self .project_view .set_user (self .current_user )
        self .project_view .set_models (self ._available_models )
        self .project_view .set_detectors (self ._available_detectors )
        self .project_view .set_audio_providers (self ._available_audio_providers )
        self ._show_project ()
        self ._refresh_project (project_id =project_id ,preferred_run_id ="")

    def _on_project_back_requested (self )->None :
        self ._show_dashboard ()
        self .refresh_dashboard ()

    def _on_project_refresh_requested (self ,project_id :str ,run_id :str )->None :
        self ._refresh_project (project_id =project_id ,preferred_run_id =run_id )

    def _on_project_run_selected (self ,project_id :str ,run_id :str )->None :
        self ._refresh_project (project_id =project_id ,preferred_run_id =run_id ,show_status =False )

    def _on_add_member_requested (self ,project_id :str ,user_login :str ,member_role :str )->None :
        self .project_view .set_loading (True ,"Adding member...")

        def task ()->None :
            self .client .add_project_member (
            project_id =project_id ,
            user_login =user_login ,
            member_role =member_role ,
            )

        def on_success (_ :Any )->None :
            self .project_view .set_status_message ("Member added.",is_error =False )
            self ._refresh_project (project_id =project_id ,preferred_run_id =self .current_project_run_id or "")
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False ),
        )

    def _on_change_member_role_requested (self ,project_id :str ,user_id :str ,member_role :str )->None :
        self .project_view .set_loading (True ,"Updating member role...")

        def task ()->None :
            self .client .update_project_member_role (
            project_id =project_id ,
            user_id =user_id ,
            member_role =member_role ,
            )

        def on_success (_ :Any )->None :
            self .project_view .set_status_message ("Member role updated.",is_error =False )
            self ._refresh_project (project_id =project_id ,preferred_run_id =self .current_project_run_id or "")

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False ),
        )

    def _on_remove_member_requested (self ,project_id :str ,user_id :str )->None :
        self .project_view .set_loading (True ,"Removing member...")

        def task ()->None :
            self .client .remove_project_member (project_id =project_id ,user_id =user_id )

        def on_success (_ :Any )->None :
            self .project_view .set_status_message ("Member removed.",is_error =False )
            self ._refresh_project (project_id =project_id ,preferred_run_id =self .current_project_run_id or "")
            self .refresh_dashboard ()

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False ),
        )

    def _refresh_project (
    self ,
    *,
    project_id :str ,
    preferred_run_id :str ,
    show_status :bool =True ,
    )->None :
        self .current_project_id =project_id 
        if show_status :
            self .project_view .set_loading (True ,"Loading project data...")

        def task ()->dict [str ,Any ]:
            project =self .client .get_project (project_id =project_id )
            members =self .client .list_project_members (project_id =project_id ).items 
            runs_page =self .client .list_processing_runs (project_id =project_id ,limit =50 ,offset =0 )
            runs =list (runs_page .items )

            selected_run_id =self ._resolve_selected_run_id (runs ,preferred_run_id =preferred_run_id )
            if selected_run_id :
                candidate =next ((run for run in runs if str (run .id )==selected_run_id ),None )
                if candidate is not None and candidate .status in {"scheduled","pending","running"}:
                    try :
                        self .client .sync_processing_run (project_id =project_id ,run_id =selected_run_id )
                        runs_page =self .client .list_processing_runs (project_id =project_id ,limit =50 ,offset =0 )
                        runs =list (runs_page .items )
                        selected_run_id =self ._resolve_selected_run_id (runs ,preferred_run_id =selected_run_id )
                    except ApiError :
                        pass 

            original_video_path =self ._ensure_project_video_cached (project_id =project_id )
            overlay_video_path :str |None =None 
            video_timeline_points :list [dict [str ,Any ]]=[]
            audio_timeline_points :list [dict [str ,Any ]]=[]
            audio_feature_series :dict [str ,list [dict [str ,float ]]]={}

            if selected_run_id :
                try :
                    artifacts =self .client .list_artifacts (project_id =project_id ,run_id =selected_run_id ).artifacts 
                except ApiError :
                    artifacts =[]

                overlay_artifact =self ._select_artifact (
                artifacts ,
                artifact_type ="video",
                path_hints =("overlay","processed"),
                )
                video_results_artifact =self ._select_artifact (
                artifacts ,
                artifact_type ="json",
                path_hints =("results","emotion"),
                )
                audio_results_artifact =self ._select_audio_results_artifact (artifacts )

                if overlay_artifact is not None :
                    cached_overlay =self ._ensure_artifact_cached (
                    project_id =project_id ,
                    run_id =selected_run_id ,
                    artifact =overlay_artifact ,
                    )
                    overlay_video_path =str (cached_overlay )

                if video_results_artifact is not None :
                    cached_video_results =self ._ensure_artifact_cached (
                    project_id =project_id ,
                    run_id =selected_run_id ,
                    artifact =video_results_artifact ,
                    )
                    raw_video_payload =self ._load_json_payload (cached_video_results )
                    if raw_video_payload is not None :
                        video_timeline_points =self ._extract_video_timeline_points (raw_video_payload )

                if audio_results_artifact is not None :
                    cached_audio_results =self ._ensure_artifact_cached (
                    project_id =project_id ,
                    run_id =selected_run_id ,
                    artifact =audio_results_artifact ,
                    )
                    raw_audio_payload =self ._load_json_payload (cached_audio_results )
                    if raw_audio_payload is not None :
                        audio_timeline_points =self ._extract_audio_timeline_points (raw_audio_payload )
                        audio_feature_series =self ._extract_audio_feature_series (raw_audio_payload )

            return {
            "project":project ,
            "members":members ,
            "runs":runs ,
            "selected_run_id":selected_run_id ,
            "video_timeline_points":video_timeline_points ,
            "audio_timeline_points":audio_timeline_points ,
            "audio_feature_series":audio_feature_series ,
            "original_video_path":original_video_path ,
            "overlay_video_path":overlay_video_path ,
            }

        def on_success (result :dict [str ,Any ])->None :
            self .current_project_id =project_id 
            self .current_project_run_id =str (result .get ("selected_run_id")or "")or None 
            self .project_view .set_project_data (
            project =result ["project"],
            members =list (result ["members"]),
            runs =list (result ["runs"]),
            selected_run_id =self .current_project_run_id ,
            video_timeline_points =list (result ["video_timeline_points"]),
            audio_timeline_points =list (result ["audio_timeline_points"]),
            audio_feature_series =dict (result ["audio_feature_series"]),
            original_video_path =str (result ["original_video_path"])if result ["original_video_path"]else None ,
            overlay_video_path =str (result ["overlay_video_path"])if result ["overlay_video_path"]else None ,
            )
            if show_status :
                self .project_view .set_status_message (
                f"Project data refreshed: {datetime .now ().strftime ('%H:%M:%S')}",
                is_error =False ,
                )

        def on_error (error :Exception )->None :
            if isinstance (error ,ApiError )and error .status_code ==401 :
                self ._handle_session_expired ()
                return 
            self .project_view .set_status_message (self ._format_error (error ),is_error =True )

        self ._run_background (
        task ,
        on_result =on_success ,
        on_error =on_error ,
        on_finished =lambda :self .project_view .set_loading (False )if show_status else None ,
        )

    def _resolve_selected_run_id (self ,runs :list [ProcessingRun ],*,preferred_run_id :str )->str |None :
        if not runs :
            return None 

        preferred =preferred_run_id .strip ()
        if preferred and any (str (run .id )==preferred for run in runs ):
            return preferred 

        return str (runs [0 ].id )

    def _project_cache_dir (self ,project_id :str )->Path :
        path =self .config .app_data_dir /"projects"/project_id 
        path .mkdir (parents =True ,exist_ok =True )
        return path 

    def _ensure_project_video_cached (self ,*,project_id :str )->str |None :
        cache_dir =self ._project_cache_dir (project_id )
        target =cache_dir /"original_video.mp4"
        if not target .exists ()or target .stat ().st_size ==0 :
            self .client .download_project_video (project_id =project_id ,target_path =target )
        return str (target )

    def _ensure_artifact_cached (self ,*,project_id :str ,run_id :str ,artifact :Artifact )->Path :
        run_dir =self ._project_cache_dir (project_id )/"runs"/run_id 
        run_dir .mkdir (parents =True ,exist_ok =True )

        artifact_name =Path (artifact .path ).name .strip ()or f"{artifact .artifact_id }.bin"
        target =run_dir /artifact_name 
        if not target .exists ()or target .stat ().st_size ==0 :
            self .client .download_artifact (
            project_id =project_id ,
            artifact_id =artifact .artifact_id ,
            run_id =run_id ,
            target_path =target ,
            )
        return target 

    def _select_artifact (
    self ,
    artifacts :list [Artifact ],
    *,
    artifact_type :str ,
    path_hints :tuple [str ,...]=(),
    )->Artifact |None :
        candidates =[item for item in artifacts if item .type .lower ()==artifact_type .lower ()]
        if not candidates :
            return None 

        for hint in path_hints :
            lowered_hint =hint .lower ()
            for item in candidates :
                if lowered_hint in item .path .lower ():
                    return item 
        return candidates [0 ]

    def _select_audio_results_artifact (self ,artifacts :list [Artifact ])->Artifact |None :
        if not artifacts :
            return None 

        explicit_audio_hints =(
        "audio_result_remote",
        "audio_result",
        "audio_solution",
        "audio_report",
        "audio/",
        "/audio_",
        )

        explicit =[
        item 
        for item in artifacts 
        if any (hint in item .path .lower ()for hint in explicit_audio_hints )
        and item .type .lower ()in {"audio_json","json"}
        ]
        if explicit :
            explicit .sort (
            key =lambda item :(
            0 if item .type .lower ()=="audio_json"else 1 ,
            0 if "audio_result_remote"in item .path .lower ()else 1 ,
            0 if "audio_result"in item .path .lower ()else 1 ,
            )
            )
            return explicit [0 ]

        type_audio_json =[item for item in artifacts if item .type .lower ()=="audio_json"]
        if type_audio_json :
            return type_audio_json [0 ]

            # Last resort: JSON artifact whose path clearly indicates audio payload.
        json_audio =[
        item 
        for item in artifacts 
        if item .type .lower ()=="json"
        and "audio"in item .path .lower ()
        and "results.json"not in item .path .lower ()
        ]
        if json_audio :
            return json_audio [0 ]
        return None 

    @staticmethod 
    def _load_json_payload (results_path :Path )->Any |None :
        if not results_path .exists ():
            return None 
        try :
            return json .loads (results_path .read_text (encoding ="utf-8"))
        except (OSError ,ValueError ):
            return None 

    @staticmethod 
    def _extract_frames_payload (raw_payload :Any )->list [dict [str ,Any ]]:
        if isinstance (raw_payload ,list ):
            return [item for item in raw_payload if isinstance (item ,dict )]
        if not isinstance (raw_payload ,dict ):
            return []

        direct_frames =raw_payload .get ("frames")
        if isinstance (direct_frames ,list ):
            return [item for item in direct_frames if isinstance (item ,dict )]

        direct_results =raw_payload .get ("results")
        if isinstance (direct_results ,list ):
            return [item for item in direct_results if isinstance (item ,dict )]

        nested_result =raw_payload .get ("result")
        if isinstance (nested_result ,dict ):
            nested_frames =nested_result .get ("frames")
            if isinstance (nested_frames ,list ):
                return [item for item in nested_frames if isinstance (item ,dict )]
            nested_results =nested_result .get ("results")
            if isinstance (nested_results ,list ):
                return [item for item in nested_results if isinstance (item ,dict )]

        return []

    def _extract_video_timeline_points (self ,raw_payload :Any )->list [dict [str ,Any ]]:
        frames =self ._extract_frames_payload (raw_payload )
        return self ._build_probability_timeline (frames ,prefer_risk =False )

    def _extract_audio_timeline_points (self ,raw_payload :Any )->list [dict [str ,Any ]]:
        frames =self ._extract_frames_payload (raw_payload )
        return self ._build_probability_timeline (frames ,prefer_risk =True )

    @staticmethod
    def _normalize_probability (raw_value :Any )->float :
        value =safe_float (raw_value ,0.0 )
        if value !=value :
            return 0.0
        if value >1.0 and value <=100.0 :
            value =value /100.0
        return max (0.0 ,min (1.0 ,value ))

    def _extract_audio_feature_series (self ,raw_payload :Any )->dict [str ,list [dict [str ,float ]]]:
        frames =self ._extract_frames_payload (raw_payload )
        result :dict [str ,list [dict [str ,float ]]]={}

        for item in frames :
            frame_time =self ._extract_frame_time (item )
            if frame_time is None :
                continue 

            features =item .get ("features")
            if isinstance (features ,dict )and features :
                for feature_name ,feature_value in features .items ():
                    key =str (feature_name ).strip ()
                    if not key :
                        continue 
                    try :
                        numeric_value =float (feature_value )
                    except (TypeError ,ValueError ):
                        continue 
                    if numeric_value !=numeric_value :
                        continue 

                    result .setdefault (key ,[]).append (
                    {"time":frame_time ,"value":numeric_value }
                    )
                continue 

                # Fallback for legacy providers: build feature series from top_features_detail.
            details =item .get ("top_features_detail")
            if not isinstance (details ,list ):
                continue 
            for detail in details :
                if not isinstance (detail ,dict ):
                    continue 
                key =str (detail .get ("name","")).strip ()
                if not key :
                    continue 

                raw_value =detail .get ("value")
                if raw_value is None :
                    raw_value =detail .get ("z")
                if raw_value is None :
                    raw_value =detail .get ("contribution")
                if raw_value is None :
                    continue 

                try :
                    numeric_value =float (raw_value )
                except (TypeError ,ValueError ):
                    continue 
                if numeric_value !=numeric_value :
                    continue 

                result .setdefault (key ,[]).append (
                {"time":frame_time ,"value":numeric_value }
                )

        for points in result .values ():
            points .sort (key =lambda item :safe_float (item .get ("time"),0.0 ))

        return {name :points for name ,points in sorted (result .items (),key =lambda item :item [0 ].lower ())}

    def _build_probability_timeline (
    self ,
    payload :list [dict [str ,Any ]],
    *,
    prefer_risk :bool ,
    )->list [dict [str ,Any ]]:
        points :list [dict [str ,Any ]]=[]
        timestamp_based :list [tuple [float ,dict [str ,float ]]]=[]

        for item in payload :
            probabilities :dict [str ,float ]={}

            if prefer_risk :
                if item .get ("deception_score")is not None :
                    probabilities ["risk"]=self ._normalize_probability (item .get ("deception_score"))
                else :
                    probs_raw =item .get ("probabilities")
                    if isinstance (probs_raw ,dict ):
                        for key ,value in probs_raw .items ():
                            clean_key =str (key ).strip ().lower ()
                            if clean_key in LIE_RISK_KEYS :
                                probabilities [clean_key ]=self ._normalize_probability (value )
                    if not probabilities :
                    # For audio-risk timeline, ignore emotion-like probabilities.
                        continue 
            else :
                probs_raw =item .get ("probabilities")
                if isinstance (probs_raw ,dict ):
                    for emotion ,value in probs_raw .items ():
                        key =str (emotion ).strip ().lower ()
                        if not key :
                            continue 
                        probabilities [key ]=self ._normalize_probability (value )

                if not probabilities :
                    emotion =str (item .get ("emotion","")).strip ().lower ()
                    confidence =self ._normalize_probability (item .get ("confidence"))
                    if emotion :
                        probabilities [emotion ]=confidence 

            if not probabilities :
                continue 

            if item .get ("time")is not None :
                points .append ({"time":max (0.0 ,safe_float (item .get ("time"),0.0 )),"probabilities":probabilities })
            elif item .get ("t_start")is not None :
                points .append ({"time":max (0.0 ,safe_float (item .get ("t_start"),0.0 )),"probabilities":probabilities })
            elif item .get ("timestamp")is not None :
                timestamp_based .append ((safe_float (item .get ("timestamp"),0.0 ),probabilities ))

        if timestamp_based :
            base_ts =min (item [0 ]for item in timestamp_based )
            for ts ,probs in timestamp_based :
                points .append ({"time":max (0.0 ,ts -base_ts ),"probabilities":probs })

        points .sort (key =lambda item :safe_float (item .get ("time"),0.0 ))
        if not points :
            return []

        all_series =sorted (
        {
        name 
        for item in points 
        for name in item .get ("probabilities",{}).keys ()
        if isinstance (item .get ("probabilities"),dict )
        }
        )
        if not all_series :
            return []

        for item in points :
            probs =item .get ("probabilities")
            if not isinstance (probs ,dict ):
                continue 
            for series_name in all_series :
                probs .setdefault (series_name ,0.0 )

        if len (points )==1 :
            return points 

        deltas :list [float ]=[]
        for idx in range (1 ,len (points )):
            delta =safe_float (points [idx ]["time"])-safe_float (points [idx -1 ]["time"])
            if delta >0 :
                deltas .append (delta )

        step =0.2 
        if deltas :
            deltas .sort ()
            step =max (0.05 ,min (1.0 ,deltas [len (deltas )//2 ]))

        max_time =max (safe_float (item ["time"])for item in points )
        densified :list [dict [str ,Any ]]=[]
        source_index =0 
        current_probs =dict (points [0 ]["probabilities"])
        t =0.0 

        while t <=max_time +1e-6 :
            while source_index +1 <len (points )and safe_float (points [source_index +1 ]["time"])<=t :
                source_index +=1 
                current_probs =dict (points [source_index ]["probabilities"])

            densified .append (
            {
            "time":round (t ,3 ),
            "probabilities":{name :self ._normalize_probability (current_probs .get (name ))for name in all_series },
            }
            )
            t +=step 

        if safe_float (densified [-1 ]["time"])<max_time :
            densified .append (
            {
            "time":round (max_time ,3 ),
            "probabilities":{name :self ._normalize_probability (current_probs .get (name ))for name in all_series },
            }
            )

        return densified 

    @staticmethod 
    def _extract_frame_time (item :dict [str ,Any ])->float |None :
        if item .get ("time")is not None :
            return max (0.0 ,safe_float (item .get ("time"),0.0 ))
        if item .get ("t_start")is not None :
            return max (0.0 ,safe_float (item .get ("t_start"),0.0 ))
        if item .get ("timestamp")is not None :
            return max (0.0 ,safe_float (item .get ("timestamp"),0.0 ))
        return None 

    def _handle_session_expired (self )->None :
        self ._reset_session ()
        self .auth_view .show_info ("Session expired. Please sign in again.")
        self ._show_auth ()

    def _reset_session (self )->None :
        self .current_user =None 
        self .current_project_id =None 
        self .current_project_run_id =None 
        self ._available_models =[]
        self ._available_detectors =["haar","mtcnn","retinaface","scrfd"]
        self ._available_audio_providers =[]
        self ._admin_users_query =""
        self ._admin_users_role =None 
        self ._admin_users_active =None 
        self ._admin_projects_query =""
        self .client .clear_session_token ()
        self .session_store .clear ()

    def _format_error (self ,error :Exception )->str :
        if isinstance (error ,ApiError ):
            return error .message 
        return f"Unknown error: {error }"
