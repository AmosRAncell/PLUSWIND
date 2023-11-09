import os
import numpy as np
import pandas as pd

# ----- User Input -----
years = [2018,2019,2020,2021]

plantInfoFile = '/Volumes/GoogleDrive/Shared drives/RE_Team_Data/IndividualREPlantProfiles/windPublicRepository/site_list_for_windPublicRepo_withSP_ARA-20220407.csv' # file matching each plant to the ISO it is in

curtMultFileForm = 'path/to/curtailmentMultipliersBy{ISO}{YEAR}.csv' # files with monthly plant-specific curtailment multipliers
curtMultIsos = ['CAISO','SPP','ISONE','MISO','PJM','NYISO']

# For ERCOT, we have the ERCOT's High Speed Limit (HSL) generation, so we use that directly instead of relying on approximated curtailment multipliers
# Our HSL files were inconsistently named and formatted by year
# ercHSLFileForm tracks the file name each year
ercHSLPath = 'path/to/folderWithHSLFiles'
ercHSLFileForm = {
	2018:'fileNameOf2018HSLData.csv',
	2019:'fileNameOf2019HSLData.csv',
	2020:'fileNameOf2020HSLData.csv',
	2021:'fileNameOf2021HSLData.csv',
}
# ercHSLCols tracks the important column names for each year
ercHSLCols = {
	2018:['gmt_int','%Y%m%d%H','MW_gen_bias_corrected_RAW'],
	2019:['gmt_int','%Y%m%d%H','MW_gen_bias_corrected_RAW'],
	2020:['Datetime GMT (Hour Beginning)','%Y-%m-%d %H:00:00+00:00','MW_gen_raw_not_curtailed'],
	2021:['gmt','%Y-%m-%d %H:00:00+00:00','MW_gen_raw_not_curtailed'],
}

genFile = 'path/to/MonthlyGenByPlant/monthlyGenByPlant_hrBegAvg_preCurtAdj_2018-2021-20230129.csv' # files with pre-curtailment-adjusted generation (e.g. the outputs of getMonthlyGenByPlant.py)

outN = 'path/to/MonthlyGenByPlant/monthlyGenByPlant_hrBegAvg_curtAdj_2018-2021-20230129.csv'
# ----------------------

# load in plant info
plantInfo = pd.read_csv(plantInfoFile,index_col='EIA_ID')

# load in raw (pre-curtailment-adjusted) monthly generation by plant
gen = pd.read_csv(genFile,index_col=['EIA_ID','Year','Month'])

# load in monthly curtailment multipliers
curtCols = [f'{m}-curInflator' for m in range(1,13)]
monthExtractor = lambda c: int(c.split('-')[0])
curtMults = {}
for iso in curtMultIsos:
	for year in years:
		df = pd.read_csv(curtMultFileForm.format(ISO=iso,YEAR=year),usecols=curtCols+['eiaID'])
		df.set_index('eiaID',inplace=True)
		df.columns = df.columns.map(monthExtractor).rename('Month')
		curtMults[(iso,year)] = df.stack().to_frame('curInflator')

curtMults = pd.concat(curtMults,names=['ISO','Year','EIA_ID','Month']).reset_index(level='ISO')
curtMults = curtMults.reorder_levels(['EIA_ID','Year','Month'])

# adjust generation for curtailment for plants we have curt multipliers for
# (no ERCOT plants should be included here as we use HSL data to account for their curtailment)
gen['curtAdjustedGen MWh'] = np.nan
idx = gen.index.intersection(curtMults.index)
gen.loc[idx,'curtMult'] = curtMults.loc[idx,'curInflator']
gen.loc[idx,'curtAdjustedGen MWh'] = gen.loc[idx,'Reported Gen MWh'] * curtMults.loc[idx,'curInflator']

# use HSL data for curtailment-adjusted generation in ERCOT
hslGen = {}
for year in years:
	gmtCol,gmtFormat,genCol = ercHSLCols[year]
	fileName = ercHSLFileForm[year]
	df = pd.read_csv(os.path.join(ercHSLPath,fileName),usecols=['EIA_ID',gmtCol,genCol])
	df[gmtCol] = pd.to_datetime(df[gmtCol],format=gmtFormat,cache=True)
	if year == 2018:
		df = df[df[gmtCol].dt.year == 2018] # as 2018 HSL file contains many years of data
	# the HSL data sometimes contains EIA_IDs that are combos of plants (e.g '56795_57095'). I exclude them from this dataset
	print(f"EIA_IDs in {year} to be excluded from HSL data: {df.loc[~df['EIA_ID'].astype(str).str.isdigit(),'EIA_ID'].unique()}")
	df = df[df['EIA_ID'].astype(str).str.isdigit()]
	df['EIA_ID'] = df['EIA_ID'].astype(int)
	# for consistent column names across the years
	df.rename(columns={gmtCol:'GMT Datetime (Hour Beginning)',genCol:'HSL_gen'},inplace=True)
	hslGen[year] = df.set_index(['EIA_ID','GMT Datetime (Hour Beginning)'])

hslGen = pd.concat(hslGen,names=['Year','EIA_ID','GMT Datetime (Hour Beginning)'])

# Sum a month of HSL generation data for a plant,
# but return np.nan if >90% of the hours have missing generation data
def sumMonthlyHSL(g):
	eiaId,year,month = g.name
	hoursInMonth = pd.Timestamp(year=year,month=month,day=1).days_in_month*24
	return g.sum() if g.notna().sum() > hoursInMonth*0.9 else np.nan

monthIdx = hslGen.index.get_level_values('GMT Datetime (Hour Beginning)').month.rename('Month')
hslGenMonthly = hslGen['HSL_gen'].groupby(['EIA_ID','Year',monthIdx]).apply(sumMonthlyHSL)

# Add HSL data to gen, leaving blank if no HSL data for a plant
idx = hslGenMonthly.index.intersection(gen.index)
gen['usesHSLGen'] = gen.index.isin(idx).astype(int)
gen['eia_ba'] = plantInfo.loc[gen.index.get_level_values('EIA_ID'),'eia_ba'].to_numpy()
gen.loc[idx,'curtAdjustedGen MWh'] = hslGenMonthly.loc[idx]

# write to CSV
gen.to_csv(outN)
