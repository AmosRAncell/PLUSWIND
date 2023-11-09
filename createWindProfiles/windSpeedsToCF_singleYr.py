import os
import re
import sys
import numpy as np
import pandas as pd

# ----- User Input -----
year = int(sys.argv[1])

models = ['ERA5','MERRA2','HRRR'] # the wind models whose speeds are being turned into CFs, e.g ['ERA5','MERRA2','HRRR']

windProfFolder = 'path/to/folderWithFilesContainingWindSpeeds' # folder with files containing wind speeds
windProfFileFormat = '(?P<EIA_ID>\d+)_(?P<YEAR>\d+)_withHRRR.csv$' # file name format of the wind speed files within windProfFolder (as a python regular expression) 

airDensityFolder = 'path/to/folderWithAirDensityFiles' # folder with air density files
airDensityFileFormat = '(?P<EIA_ID>\d+)_(?P<YEAR>\d+).csv' # file name format of air density files
 
airDensityColName = 'MERRA2 air density (kg/m^3)' # Name of column in air density files with the air density data
airDensityReference = 1.225 # air density at sea level in kg/m^3

powerCurvesFolder = 'path/to/folderWithPowerCurveFiles' # folder of power curves
powerCurveFileFormat = '(?P<SPECIFIC_POWER>\d+).csv$' # file name format of the power curves (as a python regular expression)

specificPowerFile = 'path/to/fileWithSpecificPowerForEachPlant.csv' # file with specific power by EIA_ID

outputCols = [ # the desired columns to output
	'ERA5 wind speed (m/s)',
	'MERRA2 wind speed (m/s)',
	'HRRR wind speed (m/s)',
	'MERRA2 air density (kg/m^3)',
	'ERA5 density-corrected wind speed (m/s)',
	'MERRA2 density-corrected wind speed (m/s)',
	'HRRR density-corrected wind speed (m/s)',
	'ERA5 CF (raw)',
	'ERA5 CF (density adjusted)',
	'ERA5 CF (density and loss adjusted)',
	'MERRA2 CF (raw)',
	'MERRA2 CF (density adjusted)',
	'MERRA2 CF (density and loss adjusted)',
	'HRRR CF (raw)',
	'HRRR CF (density adjusted)',
	'HRRR CF (density and loss adjusted)'
]

fOutName = './path/to/outputFolder/ERA5_MERRA2_HRRR_windSpeedAndCF_2021/{EIA_ID}_{YEAR}.csv' # file name format for output files
# ----------------------

# load in wind profile files
print('Loading in wind profiles')
windProfs = {}
for fName in os.listdir(windProfFolder):
	match = re.match(windProfFileFormat,fName)
	if not match: continue # if file doesn't match the wind profile file name format, skip it
	eiaId = int(match.group('EIA_ID'))
	yr = int(match.group('YEAR'))
	if yr != year: continue # if file is for the wrong year, skip it
	if len(windProfs) % 100 == 0: # just a progress tracker as this for loop can take a long time
		print(f'{len(windProfs)} loaded in')
	prof = pd.read_csv(os.path.join(windProfFolder,fName))
	prof['gmt'] = pd.to_datetime(prof['gmt'],format='%Y%m%d%H')
	windProfs[eiaId] = prof.set_index('gmt')

windProfs = pd.concat(windProfs,names=['EIA_ID'])
windProfs.sort_index(inplace=True) # improves performance later
windProfs.rename(columns=dict(
	(f'{model}_wind_speed_m_per_sec',f'{model} wind speed (m/s)')
	for model in models
),inplace=True) # just rename the columns to the desired format


# load in air density
print('Loading in air density files')

# parses an air density file name and returns the EIA ID if one is found and None otherwise
def eiaIdFromAirDensityFile(fName):
	match = re.match(airDensityFileFormat,fName)
	if match is None:
		return None
	return int(match.group('EIA_ID'))

# create a dictionary mapping EIA IDs to the file name of their associated air density file
airDensityFNames = dict(
	(eiaIdFromAirDensityFile(fName),fName) for fName in os.listdir(airDensityFolder)
)
for i,eiaId in enumerate(windProfs.index.unique(level='EIA_ID')):
	if i % 100 == 0: # progress tracker as this loop can take a while
		print(f'{i}/{len(windProfs.index.unique(level="EIA_ID"))} air density files loaded in')
	airDensityData = pd.read_csv(os.path.join(airDensityFolder,airDensityFNames[eiaId]))
	airDensityData['gmt'] = pd.to_datetime(airDensityData['gmt'],format='%Y%m%d%H')
	airDensityData.set_index('gmt',inplace=True)
	# Note: the next line requires 8760/8784 rows for both the wind profile and the air density data
	windProfs.loc[eiaId,'MERRA2 air density (kg/m^3)'] = airDensityData[airDensityColName].values

# Apply air density correction to the wind speeds, according to:
# WS_corrected = WS * (rho/rho_0)^(1/3)
# where rho is air density, rho_0 is air density where the power curves (to be used later) are valid for, e.g sea level
# WS is raw wind speed, and WS_corrected is the density corrected wind speed
print('Applying air density correction to wind speeds')

def airDensityCorrection(windSpeeds,airDensities,airDensityReference):
	return windSpeeds * np.power(airDensities/airDensityReference,1/3)

airDensities = windProfs['MERRA2 air density (kg/m^3)']
for modelName in models:
	windSpeeds = windProfs[f'{modelName} wind speed (m/s)']
	windProfs[f'{modelName} density-corrected wind speed (m/s)'] = airDensityCorrection(windSpeeds,airDensities,airDensityReference)

# load in power curve data
print('Loading in power curves')

# finds cut-in speed, rated-speed,cut-out speed, and the coefficients of a 10th degree polynomial to model the curved part of the power curve
# pwrCrv is a DataFrame of power curve data, with an index of wind speeds and a generation column (e.g 'CF' or 'Turbine Output')
def fitPowerCurve(pwrCrv,genCol='CF'):
	cutIn  = pwrCrv.index[pwrCrv[genCol] != 0].min()
	cutOut = pwrCrv.index[pwrCrv[genCol] != 0].max()
	rated  = pwrCrv.index[pwrCrv[genCol] == pwrCrv[genCol].max()].min()
	polySpeeds = pwrCrv.index[(pwrCrv.index >= cutIn) & (pwrCrv.index <= rated)]
	polyCoeffs = np.polyfit(polySpeeds,pwrCrv.loc[polySpeeds,genCol],10)
	return (cutIn,cutOut,rated,polyCoeffs)

powerCurves = {}
for fName in os.listdir(powerCurvesFolder):
	match = re.match(powerCurveFileFormat,fName)
	if match is None: continue # if file name doesn't match the format of a power curve file, skip it
	specificPower = int(match.group('SPECIFIC_POWER'))
	powerCurve = pd.read_csv(os.path.join(powerCurvesFolder,fName),index_col='Wind Speed (m/s)')
	powerCurve['CF'] = powerCurve['Turbine Output'] / 1500 # NOTE: If reusing this script, check that 1500 is still the maximum output!
	powerCurves[specificPower] = fitPowerCurve(powerCurve) # store the cut-in speed, rated speed, etc in powerCurves

powerCurves = pd.DataFrame.from_dict(powerCurves,orient='index',columns=['cutIn','cutOut','rated','coeffs'])
powerCurves.sort_index(inplace=True) # improves performance later
powerCurves.index.rename('Specific Power',inplace=True) # just for clarity, it isn't important otherwise

# load in Specific Powers of each plant
specificPowers = pd.read_csv(specificPowerFile,index_col='EIA_ID')

# match each plant's SP to the closest SP among the SPs of the power curves
# returns the specific power in powerCurves.index closest to the given specific power
def closestPowerCurveSP(plantSp):
	if np.isnan(plantSp):
		return np.nan
	dists = (powerCurves.index - plantSp).map(abs)
	return powerCurves.index[dists.argmin()]

specificPowers['closestPowerCurveSP'] = specificPowers['USWTDB-SP'].apply(closestPowerCurveSP) # 'USWTDB-SP contains the specific power for each plant
windProfs['pwrCrvSP'] = specificPowers.loc[windProfs.index.get_level_values('EIA_ID'),'closestPowerCurveSP'].values

# runs an np.ndarray through the power curve data in powerCurves.loc[specificPower]
# returns CFs, not generation
def evalPowerCurve(windSpeeds,specificPower):
	cutIn,cutOut,rated,polyCoeffs = powerCurves.loc[specificPower]
	gen = np.polyval(polyCoeffs,windSpeeds)
	gen[(windSpeeds < cutIn) | (windSpeeds > cutOut)] = 0
	gen[(windSpeeds >= rated) & (windSpeeds <= cutOut)] = 1
	return gen.clip(0,1) # clip gen so all negative values are replace with 0 and all values > 1 are replaced with 1. This is just in case the polynomial portion of the power curve does something weird and outputs a value outside of [0,1]

wsRawCols   = [f'{model} wind speed (m/s)'                     for model in models]
wsCorrCols  = [f'{model} density-corrected wind speed (m/s)'   for model in models]
genRawCols  = [f'{model} CF (raw)'                             for model in models]
genCorrCols = [f'{model} CF (density adjusted)'                for model in models]

wsCols = wsRawCols + wsCorrCols
genCols = genRawCols + genCorrCols

# run wind speeds through power curves
print('Running wind speeds through power curves')

for sp in windProfs['pwrCrvSP'].unique():
	idx = windProfs['pwrCrvSP'] == sp # select plants with SP matchin sp
	ws = windProfs.loc[idx,wsCols]    # select the wind speeds for those plants
	windProfs.loc[idx,genCols] = evalPowerCurve(ws,sp) # run the wind speeds through the power curve associated with sp

""" Quick Aside:
	* The above for loop can be simplified to the following two lines
	* However, I find the two-liner harder to read and it doesn't provide a significant speed improvement, so I prefer to use the above for loop

windProfs.set_index('pwrCrvSP',append=True,inplace=True) 
windProfs[genCols] = windProfs.groupby('pwrCrvSP')[wsCols].transform(lambda g: evalPowerCurve(g,g.index[0][-1])).values
"""

# apply Wake losses to generation, according to:
# When: WS < (RS - 0.5): loss = 7% (i.e., multiply power curve output by 93%) 
# When: WS >= (RS - 0.5) and WS <= (RS + 2.0): loss = 7% - (7%)(WS - RS*)/(2.5), where RS* = RS - 0.5 
# When: WS > RS+2: loss = 0%  
# where, WS = wind speed in meters per second and 
# RS = Rated speed of the turbine power curve (i.e., the first WS at which output equals its peak value)
print('Applying Wake losses to generation')

def wakeLossCorrection(ws,rs,generation):
	loss = np.zeros_like(ws) # start with all losses being 0
	loss[ws < rs - 0.5] = 0.07
	np.putmask(loss,(ws >= rs - 0.5) & (ws <= rs + 2),0.07 - 0.07 * (ws - rs + 0.5)/2.5)
	# Note: the entries of loss[ws > rs + 2] are 0 because loss started out as all zeros
	return generation * (1 - loss)

windProfs['Rated Speed'] = powerCurves.loc[windProfs['pwrCrvSP'],'rated'].values
for model in models:
	wsDensityCorr = windProfs[f'{model} density-corrected wind speed (m/s)']
	genDensityCorr = windProfs[f'{model} CF (density adjusted)']
	genWakeLossCol = f'{model} CF (density and loss adjusted)'
	windProfs[genWakeLossCol] = wakeLossCorrection(wsDensityCorr,windProfs['Rated Speed'],genDensityCorr)

# output final data to CSVs
print('Outputting wind speeds and CFs to CSVS')
for eiaId in windProfs.index.get_level_values('EIA_ID').unique():
	windProfs.loc[eiaId,outputCols].to_csv(fOutName.format(EIA_ID=eiaId,YEAR=year),index_label='gmt',date_format='%Y%m%d%H')
