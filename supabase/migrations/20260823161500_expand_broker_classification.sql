alter table public.broker_directory
  drop constraint broker_directory_classification_check,
  add constraint broker_directory_classification_check
    check (classification is null or classification in ('LOCAL', 'FOREIGN', 'BUMN'));
