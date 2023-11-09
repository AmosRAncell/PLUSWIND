# A database of hourly wind speed and estimated generation for US
##### Corresponding author: Dev Millstein (dmillstein@lbl.gov)
This repository provides the code used in creating the PLUSWIND repository (available at https://a2e.energy.gov/project/pluswind or http://doi.org/10.21947/1903602) described in Millstein, D. *et al*. A database of hourly wind speed and estimated generation for US (**insert full citation when plublished**)

The repository is broken into three folders that correspond to the order the scripts were run.
1. downloadWindspeeds - Contains the three scripts to download the meteorological data. This is the first step in creating the wind profiles.
2. createWindProfiles - Contains the scripts to turn the downloaded meteorological data from Step 1 into the wind profiles provided in the PLUSWIND repository.
3. evaluateWindProfiles - Contains the scripts to make the figures and statistics provided in Millstein, D. *et al*. (**insert full citation when published**)

Additional information on each script's function is included as comments in the scripts.

## Miscallaneous Notes:
* In all code, the term ISO refers to both ISOs and RTOs

## Brief description of scripts
##### downloadWindspeeds/
download_ERA5.py - download ERA5 data.
download_HRRR.py - download HRRR data.
download_MERRA.r - download MERRA2 data.

##### createWindProfiles/
windSpeedsToCF_singleYr.py - run wind speeds from ERA5/MERRA2/HRRR thought power curves, applying air density and loss corrections.
getHourlyGenByIso.py - Joins modelled hourly plant level generation with reported ISO-wide hourly generation, along with doing some processing/filtering/formatting.
getMonthlyGenByPlant.py - Joins modelled monthly plant level generation with reported data, along with some processing/filtering/formatting.
curtAdjustHourlyGenByIso.py - run after getHourlyGenByIso.py. Adds curtailment to the reported gen output of getHourlyGenByIso
curtAdjustMonthlyGenByPlant.py - run after getMonthlyGenByPlant.py. Adds curtailment data to the reported gen column of getMonthlyGenByPlant

##### evaluateWindProfiles/
plotDiurnalFigures_allUS.py - run after all scripts in downloadWindspeeds/ and createWindProfiles/. Creates plots of diurnal generation and coefficient of determination
summaryStatsOfWindModels_v2.py - run after all scripts in downloadWindspeeds/ and createWindProfiles/. Creates all remaining figures and statistics
