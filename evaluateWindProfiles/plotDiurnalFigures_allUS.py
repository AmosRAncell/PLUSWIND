import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ----- User Input -----
years = [2018,2019,2020,2021]

# models to compare for each year
# if you enter a list, the script will use that list for all years
# if you enter a dict, the script will use your_dict[year] as the list for that year
modelsByYear = ['MERRA2','ERA5','HRRR']

# line colors for diurnal figures, by generation source
lineColors = {
	'Reported':'dimgray',
	'MERRA2':'gold',
	'ERA5':'tab:orange',
	'HRRR':'tab:blue'
}

genByIsoFileFormat = '/Users/sesuser/Documents/HRRR/analyzingHRRR/allIsosAnalysis/out/HourlyGenByIso/hourlyGen_hrBegAvg_curtAdj_clip995_2018-2021_{ISO}-20230129.csv'

diurnalGen_outN = './../out/HourBeginningDiurnalFigures/diurnalGen_{ISO}_{YEAR_START}-{YEAR_END}_interp_hrBegAvg-20230202.pdf'
diurnalCoefOfDet_outN = './../out/HourBeginningDiurnalFigures/diurnalCoefOfDet_{ISO}_{YEAR_START}-{YEAR_END}_interp_hrBegAvg-20230202.pdf'
# ----------------------

# list of ISO names
isos = ['CAISO','ERCOT','MISO','PJM','SPP','ISONE','NYISO']

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

# load in hourly modelled and reported generation by ISO
allModels = {m for models in modelsByYear.values() for m in models}
cols = [f'{model} Gen MWh (density and loss adjusted)' for model in allModels]+['curtAdjustedGen MWh','ISO','gmt']
genByIso = []
for iso in isos:
	gen = pd.read_csv(genByIsoFileFormat.format(ISO=iso),usecols=cols)
	gen['gmt'] = pd.to_datetime(gen['gmt'],infer_datetime_format=True,cache=True)
	genByIso.append(gen)

genByIso = pd.concat(genByIso).set_index(['ISO','gmt'])

# rename columns to be easier to work with
renamer = lambda cName: cName.replace(' (density and loss adjusted)','')
genByIso.rename(columns=renamer,inplace=True)


### Part 2: Create the graphs analyzing the data ###

# plot diurnal generation by quarter
# genData is the generation data for a single ISO and year
# isoName and year are just necessary for titling the graphs
# models is the list of model names (e.g ['HRRR','ERA5','MERRA2']) whose data you want to plot
def plotDiurnalGenerationByQuarter(genData,isoName,year,models):
	# find the mean generation by hour of day for each quarter
	diurnalGen = genData.groupby([genData.index.quarter,genData.index.hour]).mean()
	maxGen = diurnalGen.max().max()
	# create axes to plot data on
	fig,axs = plt.subplots(nrows=2,ncols=2,sharex=True)
	axs = axs.flatten() # this makes it easier to loop through the 4 axes
	for i in range(4):
		ax = axs[i]
		quarter = i+1
		ax.set_title(f'Q{quarter}')
		if i in [2,3]:
			ax.set_xlabel('Hour (Local)')
		if i in [0,2]:
			ax.set_ylabel('Mean Generation (MWh)')
		# plot the diurnal generation for each generation source
		ax.plot(diurnalGen.loc[quarter,'curtAdjustedGen MWh'],label='Reported',color=lineColors['Reported'])
		for genSource in models:
			ax.plot(diurnalGen.loc[quarter,f'{genSource} Gen MWh'],label=genSource,color=lineColors[genSource])
		ax.set_ylim(bottom=0)
		#ax.set_ylim(bottom=0,top=maxGen) # make sure graphs are zero-based
		ax.set_xticks([0,6,12,18,24])
	fig.suptitle(f'{isoName} {year}')
	plt.legend(loc='lower left',ncol=4,frameon=False,bbox_to_anchor=(-1.15,2.27))
	plt.subplots_adjust(bottom=0.095,right=0.98,top=0.85,wspace=0.245)
	return fig


# plot diurnal coefficient of determination (i.e Pearson's correlation squared) by quarter
# genData is the generation data for a single ISO and year
# isoName and year are just necessary for titling the graphs
# models is the list of model names (e.g ['HRRR','ERA5','MERRA2']) whose data you want to plot
def plotDiurnalCoefOfDeterminationByQuarter(genData,isoName,year,models):
	# find the correlation between each model (e.g HRRR, ERA5, MERRA2) and the Reported generation at each hour of day and for each quarter
	diurnalCor = genData.groupby([genData.index.quarter,genData.index.hour]).corr(method='pearson').xs('curtAdjustedGen MWh',level=-1)
	diurnalCoefOfDet = diurnalCor ** 2 # coefficient of determination is the square of correlation
	# create the axes to plot data on
	fig,axs = plt.subplots(nrows=2,ncols=2,sharex=True)
	axs = axs.flatten()
	for i in range(4):
		ax = axs[i]
		quarter = i+1
		ax.set_title(f'Q{quarter}')
		if i in [2,3]:
			ax.set_xlabel('Hour (Local)')
		if i in [0,2]:
			ax.set_ylabel('$R^2$')
		# plot the diurnal coefficient of determination between each model and the reported generation
		for model in models:
			ax.plot(diurnalCoefOfDet.loc[quarter,f'{model} Gen MWh'],label=model,color=lineColors[model])
		ax.set_ylim(bottom=0,top=1)
		ax.set_xticks([0,6,12,18,24])
	plt.legend(loc='lower left',ncol=4,frameon=False,bbox_to_anchor=(-0.75,2.27))
	plt.subplots_adjust(left=0.09,bottom=0.095,right=0.98,top=0.85,wspace=0.183)
	plt.suptitle(f'{isoName} {year}')
	return fig

# create plots for each ISO and year
print('Plotting diurnal generation and coefficient of determination')

for iso in genByIso.index.unique(level='ISO'):
	# open PDFs to store the plots for iso
	genPlots = PdfPages(diurnalGen_outN.format(ISO=iso,YEAR_START=min(years),YEAR_END=max(years)))
	coefOfDetPlots = PdfPages(diurnalCoefOfDet_outN.format(ISO=iso,YEAR_START=min(years),YEAR_END=max(years)))
	for year in years:
		# select the generation data for this iso and year
		genData = genByIso.loc[(iso,str(year))]
		# convert the GMT dates to Local Time
		genData.set_index(genData.index.tz_convert(isoToTimeZone[iso]).rename('Local Time'),inplace=True)
		# save the plots to their respective PDFs
		genPlots.savefig(plotDiurnalGenerationByQuarter(genData,iso,year,modelsByYear[year]))
		coefOfDetPlots.savefig(plotDiurnalCoefOfDeterminationByQuarter(genData,iso,year,modelsByYear[year]))
		plt.close('all')
	# close the PDFs
	genPlots.close()
	coefOfDetPlots .close()
