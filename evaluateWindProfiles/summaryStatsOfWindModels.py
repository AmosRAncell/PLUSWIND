import os
from collections import OrderedDict
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ----- User Input -----
years = [2018,2019,2020,2021]

models = ['MERRA2','ERA5','HRRR']
modelColors = {
	'MERRA2':'gold',
	'ERA5':'tab:orange',
	'HRRR':'tab:blue'
}

plantInfoFile = '/Volumes/GoogleDrive/Shared drives/RE_Team_Data/IndividualREPlantProfiles/windPublicRepository/site_list_for_windPublicRepo_withSP_ARA-20220407.csv'

genType = 'hrBegAvg' # 'instant' or 'hrBegAvg'

genByIsoFileFormat = '/Users/sesuser/Documents/HRRR/analyzingHRRR/allIsosAnalysis/out/HourlyGenByIso/hourlyGen_{genType}_curtAdj_clip995_2018-2021_{ISO}-20230129.csv'
genByPlantFile = '/Users/sesuser/Documents/HRRR/analyzingHRRR/allIsosAnalysis/out/MonthlyGenByPlant/monthlyGenByPlant_{genType}_curtAdj_2018-2021-20230129.csv'

outPath = './../out/SummaryStatsAndFigs_v2/'
meanNormAnnBiasByPlant_outN = f'meanNormAnnBiasByPlant_2018-2021_{genType}-20230202.csv'
meanNormAnnAbsErrByPlant_outN = f'meanNormAnnAbsErrByPlant_2018-2021_{genType}-20230202.csv'
scatterMeanNormAnnBias_outN = f'scatterMeanNormAnnBiasByPlant_2018-2021_{genType}-20230202.pdf'
scatterMeanNormAnnAbsErr_outN = f'scatterMeanNormAnnAbsErrByPlant_2018-2021_{genType}-20230202.pdf'
medianMeanNormBiasByIso_outN = f'medianMeanNormBiasByIso_2018-2021_{genType}-20230202.csv'
medianMeanNormAbsErrByIso_outN = f'medianMeanNormAbsErrByIso_2018-2021_{genType}-20230202.csv'
meanR2ByIso_outN = f'meanR2ByIso_2018-2021_{genType}-20230202.csv'
lineFigSeasonalMeanNormBias_outN = f'lineFigSeasonalMeanNormBiasByIso_2018-2021_{genType}-20230202.pdf'
lineFigSeasonalMeanNormAbsErr_outN = f'lineFigSeasonalMeanNormAbsErrByIso_2018-2021_{genType}-20230202.pdf'
lineFigSeasonalMeanR2_outN = f'lineFigSeasonalMeanR2ByIso_2018-2021_{genType}-20230202.pdf'
# ----------------------

# list of ISO names
isos = ['CAISO','ERCOT','MISO','PJM','SPP','ISONE','NYISO']

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

### Part 1: Load in, filter, and format data ###

# load in plant info file
plantInfo = pd.read_csv(plantInfoFile,index_col='EIA_ID')
plantInfo['ISO'] = plantInfo['eia_ba'].replace(baToIso)

# load in hourly modelled and reported generation by ISO
genByIso = []
for iso in isos:
	gen = pd.read_csv(genByIsoFileFormat.format(genType=genType,ISO=iso))
	gen['gmt'] = pd.to_datetime(gen['gmt'],infer_datetime_format=True,cache=True)
	genByIso.append(gen)

genByIso = pd.concat(genByIso).set_index(['ISO','gmt'])

# load in monthly modelled and reported generation by plant
genByPlant = pd.read_csv(genByPlantFile.format(genType=genType))
genByPlant['Quarter'] = (genByPlant['Month']-1)//3 + 1
genByPlant.set_index(['EIA_ID','Year','Quarter','Month'],inplace=True)

# exclude the first 12 months of operation for each plant
plants = genByPlant.index.get_level_values('EIA_ID')
cods = plantInfo.loc[plants,['eia_COD_Year','eia_COD_Month']].rename(columns={
	'eia_COD_Year':'year',
	'eia_COD_Month':'month'
})
cods['day'] = 1
cods = pd.to_datetime(cods,utc=True)
postTeething = cods + pd.DateOffset(years=1)
idxDate = pd.to_datetime(genByPlant.index.map(lambda x: f'{x[1]}-{x[2]}-01'),format='%Y-%m-%d',utc=True)
genByPlant = genByPlant[idxDate >= postTeething]

# exclude months where reported generation is 0, negative, or missing
posNotNaN = (genByPlant['curtAdjustedGen MWh'] > 0) & (genByPlant['curtAdjustedGen MWh'].notna())
genByPlant = genByPlant[posNotNaN]

# by plant, exclude years without all 12 months of data
genByPlant = genByPlant.groupby(['EIA_ID','Year']).filter(lambda g: len(g) == 12)

# Part 2: Calculate summary statistics

# find mean normalized annual bias (MNAB) and mean normalized absolute error (MNAE) by plant
modGenCols = [f'{model} Gen MWh ({gtype})' for model in models for gtype in ['raw','density adjusted','density and loss adjusted']]
resByPlant = genByPlant[modGenCols].sub(genByPlant['curtAdjustedGen MWh'],axis=0)

normAnnBiasByPlant = resByPlant.sum(level=['EIA_ID','Year']).div(
	genByPlant['curtAdjustedGen MWh'].sum(level=['EIA_ID','Year']),axis=0
)
MNABByPlant = normAnnBiasByPlant.mean(level='EIA_ID')

normAnnErrByPlant = resByPlant.abs().sum(level=['EIA_ID','Year']).div(
	genByPlant['curtAdjustedGen MWh'].sum(level=['EIA_ID','Year']),axis=0
)
MNAAEByPlant = normAnnErrByPlant.mean(level='EIA_ID')

MNABByPlant.to_csv(os.path.join(outPath,meanNormAnnBiasByPlant_outN))
MNAAEByPlant.to_csv(os.path.join(outPath,meanNormAnnAbsErrByPlant_outN))

# find the median mean normalized annual bias/absolute error by ISO
def findMediansByIso(df):
	isos = plantInfo.loc[df.index,'ISO']
	return df.groupby(isos).median()

medMNABByIso = findMediansByIso(MNABByPlant)
medMNAAEByIso = findMediansByIso(MNAAEByPlant)

# scatter the mean normalized annual bias/error by plant
def scatterWithJitter_allModels(df,colForm,title,yLabel,modelColors,jitterMag=0.05,zeroLine=True,yLims=None,figAx=None,legend=True):
	rng = np.random.default_rng(12345)
	fig,ax = figAx if figAx is not None else plt.subplots(1,1)
	if zeroLine:
		ax.axhline(0,color='gray',alpha=0.4)
	for i,iso in enumerate(isos):
		isoDf = df[plantInfo.loc[df.index,'ISO'] == iso]
		jitter = rng.random(len(isoDf))*2*jitterMag-jitterMag
		for model,centerOff in zip(models,[-0.2,0,0.2]):
			col = colForm.format(model)
			ax.scatter(i+centerOff+jitter,isoDf[col],label=model,s=9,c=modelColors[model])
			ax.hlines(y=isoDf[col].median(),xmin=i+centerOff-jitterMag*2,xmax=i+centerOff+jitterMag*2,color='black',linewidth=2,label='Median')
	ax.set_xticks(range(len(isos)))
	ax.set_xticklabels(isos)
	ax.set_title(title)
	ax.set_ylabel(yLabel)
	if yLims:
		ax.set_ylim(*yLims)
	if legend:
		handles, labels = ax.get_legend_handles_labels()
		by_label = OrderedDict(zip(labels, handles))
		by_label.move_to_end('Median')
		ax.legend(handles=by_label.values(),labels=by_label.keys(),frameon=False,prop={'size':9},loc='upper right',bbox_to_anchor=(1.015,1))
	fig.subplots_adjust(left=0.15,bottom=0.07,right=0.98,top=0.9)
	return fig

# make mean normalized annual bias figures
pp = PdfPages(os.path.join(outPath,scatterMeanNormAnnBias_outN))
yLabel = 'Mean Normalized Annual Bias (Modeled - Observed)'
rawFig = scatterWithJitter_allModels(MNABByPlant,'{} Gen MWh (raw)','Mean Normalized Annual Bias by Plant:\nRaw Gen',yLabel,modelColors,yLims=(-1.1,1.5))
pp.savefig(rawFig)
daFig = scatterWithJitter_allModels(MNABByPlant,'{} Gen MWh (density adjusted)','Mean Normalized Annual Bias by Plant:\nDensity Adjusted Gen',yLabel,modelColors,yLims=(-1.1,1.5))
pp.savefig(daFig)
dlaFig = scatterWithJitter_allModels(MNABByPlant,'{} Gen MWh (density and loss adjusted)','Mean Normalized Annual Bias by Plant:\nDensity and Loss Adjusted Gen',yLabel,modelColors,yLims=(-1.1,1.5))
pp.savefig(dlaFig)
pp.close()

# make mean normalized annual error figures
pp = PdfPages(os.path.join(outPath,scatterMeanNormAnnAbsErr_outN))
rawFig = scatterWithJitter_allModels(MNAAEByPlant,'{} Gen MWh (raw)','Mean Normalized Annual Error by Plant: Raw Gen','Mean Normalized Annual Error',modelColors,yLims=(0,1.5),zeroLine=False)
pp.savefig(rawFig)
daFig = scatterWithJitter_allModels(MNAAEByPlant,'{} Gen MWh (density adjusted)','Mean Normalized Annual Error by Plant: Density Adjusted Gen','Mean Normalized Annual Error',modelColors,yLims=(0,1.5),zeroLine=False)
pp.savefig(daFig)
dlaFig = scatterWithJitter_allModels(MNAAEByPlant,'{} Gen MWh (density and loss adjusted)','Mean Normalized Annual Error by Plant:\nDensity and Loss Adjusted Gen','Mean Normalized Annual Error',modelColors,yLims=(0,1.5),zeroLine=False)
pp.savefig(dlaFig)
pp.close()

# calculate mean normalized quarterly bias (MNQB) and absolute error (MNQAE) by plant
normAnnQuartBiasByPlant = resByPlant.sum(level=['EIA_ID','Year','Quarter']).div(
	genByPlant['curtAdjustedGen MWh'].sum(level=['EIA_ID','Year','Quarter']),axis=0
)
MNQBByPlant = normAnnQuartBiasByPlant.mean(level=['EIA_ID','Quarter'])

normAnnQuartErrByPlant = resByPlant.abs().sum(level=['EIA_ID','Year','Quarter']).div(
	genByPlant['curtAdjustedGen MWh'].sum(level=['EIA_ID','Year','Quarter']),axis=0
)
MNQAEByPlant = normAnnQuartErrByPlant.mean(level=['EIA_ID','Quarter'])

# by ISO, find median quarterly mean normalized bias/error over all plants in the ISO
def findMediansByIsoQuarter(df):
	isos = plantInfo.loc[df.index.get_level_values('EIA_ID'),'ISO'].to_numpy()
	return df.groupby([isos,'Quarter']).median()

medMNQBByIso = findMediansByIsoQuarter(MNQBByPlant)
medMNQAEByIso = findMediansByIsoQuarter(MNQAEByPlant)

# calculate R^2
yrIdx = genByIso.index.get_level_values('gmt').year.rename('Year')
quarterIdx = genByIso.index.get_level_values('gmt').quarter.rename('Quarter')
meanAnnR2ByIso = (
	genByIso.groupby(['ISO',yrIdx])
	.corr(method='pearson')
	.xs('curtAdjustedGen MWh',level=-1)
	.mean(level='ISO')
)
meanQuartR2ByIso = (
	genByIso.groupby(['ISO',yrIdx,quarterIdx])
	.corr(method='pearson')
	.xs('curtAdjustedGen MWh',level=-1)
	.mean(level=['ISO','Quarter'])
)


# combine the quarterly and annual metrics (mean normalized bias, mean normalized absolute error, mean R^2) into single DataFrames
def concatAnnualQuarterly(annual,quarterly):
	# add 'TimePeriod' level to annual's index, analogous to the 'Quarter' level of quarterly
	annualIdx = pd.Index(['Annual']*len(annual),name='TimePeriod')
	annual.set_index(annualIdx,append=True,inplace=True)
	return pd.concat([annual,quarterly]).sort_index()

medMNBByIso  = concatAnnualQuarterly(medMNABByIso,medMNQBByIso)
medMNAEByIso = concatAnnualQuarterly(medMNAAEByIso,medMNQAEByIso)
meanR2ByIso  = concatAnnualQuarterly(meanAnnR2ByIso,meanQuartR2ByIso)

medMNBByIso.to_csv(os.path.join(outPath,medianMeanNormBiasByIso_outN))
medMNAEByIso.to_csv(os.path.join(outPath,medianMeanNormAbsErrByIso_outN))
meanR2ByIso[modGenCols].to_csv(os.path.join(outPath,meanR2ByIso_outN))

# plot annual and quarterly values as 5 lines per ISO
# (one line per quarter, and one for annual)
def plotAllTimeAndQuarterlyMetricsByIso(values,col,yLabel,title,lineLen,colors,yLims=None,zeroLine=False):
	fig,ax = plt.subplots(1,1)
	#isos = values.index.unique(level='ISO')
	values = values.loc[isos]
	starts = np.arange(len(isos)) # start of each ISO's lines
	# plot the all-time values
	ax.hlines(values[col].xs('Annual',level='TimePeriod'),
		xmin=starts,xmax=starts+lineLen,
		color=colors['Annual'],label='Annual',linewidth=3
	)
	# plot quarterly values
	for q in range(1,5):
		ax.hlines(values[col].xs(q,level='TimePeriod'),
			xmin=starts+lineLen*q,xmax=starts+lineLen*(q+1),
			color=colors[q],label=f'Q{q}',linewidth=3
		)
	if zeroLine:
		ax.axhline(0,color='gray',alpha=0.3,zorder=1)
	# format x and y axes
	ax.set_xticks(starts+2.5*lineLen)
	ax.set_xticklabels(isos)
	ax.set_ylabel(yLabel)
	if yLims is not None:
		ax.set_ylim(*yLims)
	# make legend
	ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(0.5,1.08),ncol=5)
	# title and adjust figure
	ax.set_title(title,fontsize=10)
	fig.subplots_adjust(left=0.125,bottom=0.07,right=0.98,top=0.86)
	return fig

allTimeColor = 'black'
quarters = [1,2,3,4]
qColors = dict(zip(quarters,plt.get_cmap('Blues')([0.8,0.6,0.4,0.2])))
colors = {'Annual':'black',**qColors}

# plot mean normalized biases
pp = PdfPages(os.path.join(outPath,lineFigSeasonalMeanNormBias_outN))
for model in models:
	col = f'{model} Gen MWh (density and loss adjusted)'
	yLabel = 'Median of Mean Normalized Bias (Modeled - Observed)'
	title = f'Seasonal Medians of ISO-Wide Mean Normalized Biases for {model}:\nDensity and Loss Adjusted Gen\n'
	fig = plotAllTimeAndQuarterlyMetricsByIso(medMNBByIso,col,yLabel,title,0.15,colors,yLims=(-0.9,0.7),zeroLine=True)
	pp.savefig(fig)

pp.close()

# plot mean normalized absolute errors
pp = PdfPages(os.path.join(outPath,lineFigSeasonalMeanNormAbsErr_outN))
for model in models:
	col = f'{model} Gen MWh (density and loss adjusted)'
	yLabel = 'Median of Mean Normalized Absolute Error'
	title = f'Seasonal Medians of ISO-Wide Mean Normalized Absolute Errors for {model}:\nDensity and Loss Adjusted Gen\n'
	fig = plotAllTimeAndQuarterlyMetricsByIso(medMNAEByIso,col,yLabel,title,0.15,colors,yLims=(0,0.9))
	pp.savefig(fig)

pp.close()

# plot mean R^2
pp = PdfPages(os.path.join(outPath,lineFigSeasonalMeanR2_outN))
for model in models:
	col = f'{model} Gen MWh (density and loss adjusted)'
	yLabel = 'Mean $R^2$'
	title = f'Seasonal Mean $R^2$ for {model}:\nDensity and Loss Adjusted Gen\n'
	fig = plotAllTimeAndQuarterlyMetricsByIso(meanR2ByIso,col,yLabel,title,0.15,colors,yLims=(0,1))
	pp.savefig(fig)

pp.close()
