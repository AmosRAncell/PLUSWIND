import os
import numpy as np
import pandas as pd

# ----- User Input -----
years = [2018,2019,2020,2021]

# models to compare for each year
# if you enter a list, the script will use that list for all years
# if you enter a dict, the script will use your_dict[year] as the list for that year
modelsByYear = ['ERA5','MERRA2','HRRR']

hourBegAvg = True # True if the models in instantModels should have their generation hour-beginning averaged, False otherwise
instantModels = ['ERA5','HRRR'] # only populate if hourBegAvg is True. Otherwise, this variable is not used

plantInfoFile = 'path/to/fileWithPlantSpecifics.csv' # file containing, for each plant (indexed by EIA_ID): capacity (MW), the ISO it is in, the COD year and month, and whether the plant was retrofitted in a given year or not

genProfFolder = 'path/to/modelledGenProfiles/ERA5_MERRA2_HRRR_windSpeedAndCF_2018-2020' # folder with the modelled generation profiles for each plant, 2018-2020
genProfFormat = '{EIA_ID}_{YEAR}.csv' # file name format for each modelled generation profile

eia923FileFormat = 'path/to/EIAForm923FilesByYear/formatted_EIA923_Schedules_2_3_4_5_M_12_{YEAR}_Final_Revision.xlsx' # EIA 923 file name format

gen2021Folder = 'path/to/modelledGenProfiles2021/ERA5_MERRA2_HRRR_windSpeedAndCF_2021' # folder with the modelled generation profiles for each plant, 2021
gen2021ProfFormat = '{EIA_ID}_{YEAR}.csv'

outN = './../out/MonthlyGenByPlant/monthlyGenByPlant_hrBegAvg_preCurtAdj_2018-2021-20230129.csv'
# ----------------------

# crosswalk between BA names of ISOs and the ISO names
baToIso = {
	'CISO':'CAISO',
	'ERCO':'ERCOT',
	'MISO':'MISO' ,
	'PJM' :'PJM'  ,
	'SWPP':'SPP'  ,
	'ISNE':'ISONE',
	'NYIS':'NYISO'
}
# crosswalk between ISO names and time zomes
isoToTimeZone = {
	'CAISO':'US/Pacific',
	'ERCOT':'US/Central',
	'MISO' :'US/Central',
	'PJM'  :'US/Eastern',
	'SPP'  :'US/Central',
	'ISONE':'US/Eastern',
	'NYISO':'US/Eastern'
}

if isinstance(modelsByYear,list):
	modelsByYear = {year:modelsByYear for year in years}
if not isinstance(modelsByYear,dict):
	raise TypeError(f'modelsByYear must either be a list, e.g ["HRRR","ERA5","MERRA2"], or a dict, e.g {{2018:["ERA5","MERRA2"],2019:["HRRR"]}}. You entered a {type(modelsByYear)}')

### Part 1: Load in, filter, and format data ###

# load in plant info
plantInfo = pd.read_csv(plantInfoFile,index_col='EIA_ID')

# load in EIA 923 data
print('Loading in EIA 923 data')

eia923 = {}
months = ['January','February','March','April','May','June','July','August','September','October','November','December']
eiaGenCols = [f'Netgen {month}' for month in months]
for year in years:
	print(year)
	eia923Data = pd.read_excel(eia923FileFormat.format(YEAR=year),skiprows=5,index_col='Plant Id')
	eia923Data = eia923Data[eia923Data['AER\nFuel Type Code'] == 'WND']
	eia923[year] = eia923Data[eiaGenCols].groupby('Plant Id').sum() # some plants have generation data reported in multiple rows. This sums that data into a single row

eia923 = pd.concat(eia923,names=['Year'])

"""
Filter the plant list: for each year, choose only plants that
	* are in CAISO (CISO), ERCOT (ERCO), MISO, SPP (SWPP), PJM, ISONE (ISNE), or NYISO (NYIS)
	* we have MW capacity for (used to turn modelled CFs into generation)
	* we have a COD for
	* have a CF (according to EIA923 data) between 20% and 70% inclusive
	* aren't repowered in any year **** NOTE: This is different from getHourlyGenByIso.py! ****
	* We have modelled CFs for

We also drop all hours of modelled generation that are before a plant's COD
"""

# calculates the CF of a plant in a given year according to that year's EIA 923 data
def CF(eiaId,yr):
	if (yr,eiaId) not in eia923.index or eiaId not in plantInfo.index:
		return np.nan
	hoursIY = 8784 if yr % 4 == 0 and not (yr % 100 == 0 and yr % 400 != 0) else 8760
	return eia923.loc[(yr,eiaId),eiaGenCols].sum() / (hoursIY * plantInfo.loc[eiaId,'USWTDB-MW'])

eia923CF = np.vectorize(CF,excluded = ['yr']) # excluded = ['yr'] means only the eiaId parameter will be vectorized

# Apply the filters described above for a specified year
def filterPlantList(year):
	# start with the entire list of plants we have information for
	plantList = plantInfo.index
	# choose plants that are in CAISO (CISO), ERCOT (ERCO), MISO, SPP (SWPP), PJM, ISONE (ISNE), or NYISO (NYIS)
	inAnIso = plantInfo['eia_ba'].isin(baToIso.keys()).values
	# choose plants we have MW capacity for
	haveCapacity = plantInfo['USWTDB-MW'].notna().values
	# choose plants we have a COD for
	haveCODYear = plantInfo['eia_COD_Year'].notna().values
	haveCODMonth = plantInfo['eia_COD_Month'].notna().values
	haveCOD = haveCODYear & haveCODMonth
	# choose plants whose reported CF (based on EIA 923 data) is between 0.2 and 0.7 inclusive
	CFs = eia923CF(plantList,year)
	highEnoughCF = CFs >= 0.2
	lowEnoughCF = CFs <= 0.7
	# choose plants not repowered in year
	notRepowered = (plantInfo['USWTDB-Retrofit'] != 1).values
	# apply all above filters
	allFilters = inAnIso & haveCapacity & haveCOD & highEnoughCF & lowEnoughCF & notRepowered
	return plantList[allFilters]

# create a plant list for each year
print('Filtering plant lists')

plantLists = {yr:filterPlantList(yr) for yr in years}

# load in modelled generations for all plants in plantList
print('Loading in modelled generation')

def columnsToLoadIn(year):
	modCFCols = ([f'{model} CF (raw)' for model in modelsByYear[year]]
		     + [f'{model} CF (density adjusted)' for model in modelsByYear[year]]
		     + [f'{model} CF (density and loss adjusted)' for model in modelsByYear[year]])
	return modCFCols+['gmt']

modGen = {}
for year in years:
	if year == 2021:
		# 2021's modelled generation is in a different format from the other years
		# so I handle it in a separate part of the code below
		continue
	cols = columnsToLoadIn(year)
	for i,eiaId in enumerate(plantLists[year]):
		fName = genProfFormat.format(EIA_ID=eiaId,YEAR=year)
		if not os.path.exists(os.path.join(genProfFolder,fName)):
			continue
		if i % 100 == 0: print(f'{i}/{len(plantLists[year])} generation profiles done for {year}')
		genProf = pd.read_csv(os.path.join(genProfFolder,fName),usecols=cols)
		genProf['gmt'] = pd.to_datetime(genProf['gmt'],format='%Y%m%d%H',utc=True)
		modGen[(year,eiaId)] = genProf.set_index('gmt')


# Now I load in 2021's modelled generation
cols2021 = columnsToLoadIn(2021)
for i,eiaId in enumerate(plantLists[2021]):
	fName = gen2021ProfFormat.format(EIA_ID=eiaId,YEAR=2021)
	if not os.path.exists(os.path.join(gen2021Folder,fName)):
		continue
	if i % 100 == 0: print(f'{i}/{len(plantLists[2021])} generation profiles done for year 2021')
	genProf = pd.read_csv(os.path.join(gen2021Folder,fName),usecols=cols2021)
	genProf['gmt'] = pd.to_datetime(genProf['gmt'],format='%Y%m%d%H',utc=True)
	modGen[(2021,eiaId)] = genProf.set_index('gmt')


modGen = pd.concat(modGen,names=['Year','EIA_ID'])
modGen.sort_index(inplace=True) # improves performance later

# drop hours of modelled generation before a plant's COD

# first we create a Series with all of the CODs
modPlants = modGen.index.get_level_values('EIA_ID')
cods = plantInfo.loc[modPlants,['eia_COD_Year','eia_COD_Month']]
cods.rename(columns={'eia_COD_Year':'year','eia_COD_Month':'month'},inplace=True) # required for pd.to_datetime to work nicely
cods['day'] = 1
cods = pd.to_datetime(cods,utc=True)
# now we only choose hours after a plant's COD
modGen = modGen[modGen.index.get_level_values('gmt') >= cods]

# update plantLists to reflect which plants we can't use because we don't have modelled generation data for them
for year in years:
	plantLists[year] = modGen.loc[year].index.unique(level='EIA_ID')

# modGen currently only has CF data, not generation data
# turn modGen's CF data into generation data
# do this inplace because otherwise modGen uses too much memory
caps = plantInfo.loc[modGen.index.get_level_values('EIA_ID'),'USWTDB-MW']
for cfCol in modGen.columns:
	modGen[cfCol] = modGen[cfCol].mul(caps.to_numpy(),axis=0)

modGenCols = [c.replace('CF','Gen MWh') for c in modGen.columns]
modGen.rename(columns=dict(zip(modGen.columns,modGenCols)),inplace=True)


# NOTE Start of quick Spot Checking
# count longest run of NaNs per EIA_ID
print('counting length of NaN runs to ensure interpolation is the right nan-filling method')
def longestNaN(g):
	isna = g.isna()
	runs = isna*(g.groupby((isna != isna.shift()).cumsum()).cumcount()+1)
	return runs.max()

rawNanRuns = modGen['HRRR Gen MWh (raw)'].groupby('EIA_ID').apply(longestNaN)
daNanRuns = modGen['HRRR Gen MWh (density adjusted)'].groupby('EIA_ID').apply(longestNaN)
dlaNanRuns = modGen['HRRR Gen MWh (density and loss adjusted)'].groupby('EIA_ID').apply(longestNaN)

print('max length of run of consecutive NaNs in HRRR raw:',rawNanRuns.max())
print('max length of run of consecutive NaNs in HRRR da:',daNanRuns.max())
print('max length of run of consecutive NaNs in HRRR dla:',dlaNanRuns.max())

# guarantee the index for each plant goes up by 1 hour each loc
oneHour = pd.Timedelta(hours=1)
def idxBy1hour(g):
	g2 = g.reset_index(['Year','EIA_ID'],drop=True)
	return ((g2.index.shift(1,freq='H') - g2.index) == oneHour).all()

assert modGen.groupby('EIA_ID').apply(idxBy1hour).all()
# NOTE End of quick Spot Checking

# interpolate missing values
print('Interpolating missing values')
colsWithNaNs = [c for c in modGen.columns if modGen[c].hasnans]
print(f'{colsWithNaNs} have missing values, so interpolating them')
modGen[colsWithNaNs] = modGen[colsWithNaNs].groupby('EIA_ID').transform(lambda g: g.reset_index(['Year','EIA_ID'],drop=True).interpolate(method='time'))

if hourBegAvg:
	print('Hour-beginning Averaging generation for:',instantModels)
	# find hour-beginning average gen for specified models
	def hourBeginningAvg(g):
		return (g + g.shift(-1,fill_value=g.iloc[-1]))/2

	# hourBeginningAvg(g) could also be implemented as:
	# def hourBeginningAvg(g):
	# 	return g.rolling(2).mean().shift(-1).fillna(g.iloc[-1])

	for model in instantModels:
		cols = [f'{model} Gen MWh (raw)',f'{model} Gen MWh (density adjusted)',f'{model} Gen MWh (density and loss adjusted)']
		for col in cols:
			modGen[col] = modGen[col].groupby('EIA_ID').transform(hourBeginningAvg)

# aggregate modelled plant level generation to monthly totals
months = modGen.index.get_level_values('gmt').month.rename('Month')
monthlyModGen = modGen.groupby(['EIA_ID','Year',months]).sum()

monthOrder = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
renamer = lambda c: monthOrder[c.replace('Netgen ','')]
eia923 = eia923.rename(columns=renamer).rename_axis('Month',axis=1)
eia923 = eia923.stack().reorder_levels(['Plant Id','Year','Month'])
eia923.index.set_names('EIA_ID',level='Plant Id',inplace=True)

# NOTE Start of quick Spot Check
assert monthlyModGen.index.unique(level='EIA_ID').isin(eia923.index.unique(level='EIA_ID')).all()
assert (eia923.groupby(['EIA_ID','Year']).count().unique() == [12]).all()

assert (plantInfo.loc[monthlyModGen.index.unique(level='EIA_ID'),'USWTDB-Retrofit'] != 1).all()
for yr,pl in plantLists.items():
	for eiaId in pl:
		assert (plantInfo.at[eiaId,'USWTDB-Retrofit'] == 1) ^ ((eiaId,yr) in monthlyModGen.index)
# NOTE End of quick Spot Check

# add reported gen as a column to genByIso so that all generation data is in a single DataFrame
monthlyModGen['Reported Gen MWh'] = eia923

monthlyModGen.dropna(inplace=True)
monthlyModGen.to_csv(outN)
