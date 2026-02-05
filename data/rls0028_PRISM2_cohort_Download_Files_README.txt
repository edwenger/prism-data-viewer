README for PRISM2 ICEMR Cohort Download Files:


General notes:

• Column headers for each data file contain the variable label used on the ClinEpiDB.org website along with the Internationalized Resource Identifier (IRI) in brackets. 
• Each variable on ClinEpiDB.org has been mapped to an ontology term via the IRI. This approach generates a unified semantic framework, where the same variables across different studies are mapped to the same ontology term. IRIs can be searched on ontobee.org. Note that while most ontology terms used in ClinEpiDB are from existing OBO Foundry ontologies, some are placeholder terms that are created as needed and may not be published yet. 
• PRISM2_cohort_ontologyMetadata.txt links variables to their original study labels so users can reference study data collection forms and data dictionaries to learn more about each variable. 
• Delimited text files are used to store data. Each line represents a single household, participant, participant repeated measure, etc. Each line has fields separated by a tab delimiter. 
• If a variable has multiple values for a given participant/participant repeated measure/etc., values will be in a quoted, comma-separated list.

• Note that large file sizes may cause Excel to crash. We recommended using R (https://www.r-project.org/, a free software environment for statistical computing) instead. To read large files into R, we recommend using the fread( ) function from the data.table package. For example: 
	install.packages("data.table")
	library(data.table)
	setwd("~/Downloads")
	d <- fread("MAL-ED_phase2.txt") 
• If you choose to use Excel: 
   ◦ For a primer on how to open tab delimited .txt files in Excel, see: https://support.microsoft.com/en-us/office/import-or-export-text-txt-or-csv-files-5250ac4c-663c-47ce-937b-339e391393ba 
   ◦ When opening data files in Excel, date variables may read "00:00.0" for all values. This is not a data error, but will require reformatting the column using Excel’s ‘Text Import Wizard’ to obtain the actual data. See: https://support.office.com/en-us/article/text-import-wizard-c5b02af6-fda1-4440-899f-f78bafe41857#ID0EAAEAAA=Office_2010_-_Office_2016 





PRISM2_cohort_ontologyMetadata.txt, the ontology term association file includes the columns: 
• iri -- Internationalized Resource Identifier (IRI) assigned to variable (Example: "BFO_0000015") 
• label -- Displayed as variable name on ClinEpiDB (Example: "Observation type") 
• type -- Whether data is formatted as number, string, or date. If empty, row belongs to parent term without data 
• parentLabel -- Term the variable falls directly under in the variable tree on ClinEpiDB (Example: "Observation") 
• category -- Highest level parent term (Household, Participant, Participant repeated measure, etc.) variable falls under (Example: "Participant repeated measure") 
• definition -- Study specific description for variable that is displayed on ClinEpiDB under the label when variable is selected 
• min, max, average, median, upper_quartile, lower_quartile -- Provided for number and date variables 
• number_distinct_values -- Count of all possible values for variable 
• distinct_values -- Quoted, comma-separated list of all possible values for string variable 
• variable -- Column header, or variable name, from original data files. Quoted, comma-separated list if multiple variables from original data files were mapped to one ontology term (Example: "visittype") 



Data Files:

• Key identifiers: 
  ◦ Household_Id: unique identifier given to every household 
  ◦ Household_repeated_measure_Id: unique identifier given to every mosquito collection for every household

  ◦ Participant_Id: unique identifier given to every participant 
  ◦ Participant_repeated_measure_Id: unique identifier given to every unique observation for every participant 
  ◦ Sample_Id: unique identifier given to every sample


1. PRISM2_cohort_Households.txt 
   • Key identifiers: Household_Id 
   • 1 row for each household 

2. PRISM2_cohort_Participants.txt 
   • Key identifiers: Participant_Id, Household_Id 
   • 1 row for each participant 

3. PRISM2_cohort_Participant_repeated_measures.txt 
   • Key identifiers: Participant_repeated_measure_Id, Participant_Id, Household_Id 
   • 1 row for each day of observation for each participant 

4. PRISM2_cohort_Samples.txt 
   • Key identifiers: Sample_Id, Participant_repeated_measure_Id, Participant_Id, Household_Id 
   • 1 row for each set of samples from an observation 

5. PRISM2_cohort_Household_repeated_measures.txt 
   • Key identifiers: Household_repeated_measure_Id, Household_Id 
   • 1 row for each light trap collection 

6. PRISM2_cohort.txt 
   • Merges the files indicated below using key identifiers: Household_Id, Household_repeated_measure_Id, Participant_Id, Participant_repeated_measure_Id, and Sample_Id 
	◦ PRISM2_cohort_Households.txt 
	◦ PRISM2_cohort_Household_repeated_measures.txt 
	◦ PRISM2_cohort_Participants.txt 
	◦ PRISM2_cohort_Participant_repeated_measures.txt 
	◦ PRISM2_cohort_Samples.txt 
Release history: First released August 27th, 2020 (release 13). Updated November 5, 2020 (release 14) to change the IRI for "Diarrhea". See "replaces" in the Ontology Metadata download file to view all IRIs that were updated. New variables about transmission, membrane feeding, and haplotypes and complexity of infection added in March 16, 2021 (release 16). Updated in March 2022 (release 21) to reformat data for the new version of ClinEpiDB. Some variables may have moved and/or have updated labels. 