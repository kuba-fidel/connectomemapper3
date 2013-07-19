# Copyright (C) 2009-2012, Ecole Polytechnique Federale de Lausanne (EPFL) and
# Hospital Center and University of Lausanne (UNIL-CHUV), Switzerland
# All rights reserved.
#
#  This software is distributed under the open-source license Modified BSD.

""" Reconstruction methods and workflows
""" 

# General imports
import re
import os
from traits.api import *
from traitsui.api import *
import pkg_resources

import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.diffusion_toolkit as dtk
import nipype.interfaces.mrtrix as mrtrix # DR: Might be used directly in the nipype
import nipype.interfaces.camino as camino
from nipype.utils.filemanip import split_filename

from nipype.interfaces.base import CommandLine, CommandLineInputSpec,\
    traits, TraitedSpec, BaseInterface, BaseInterfaceInputSpec
import nipype.interfaces.base as nibase

# Reconstruction configuration
    
class DTK_recon_config(HasTraits):
    imaging_model = Str
    maximum_b_value = Int(1000)
    gradient_table_file = Enum('siemens_06',['mgh_dti_006','mgh_dti_018','mgh_dti_030','mgh_dti_042','mgh_dti_060','mgh_dti_072','mgh_dti_090','mgh_dti_120','mgh_dti_144',
                          'siemens_06','siemens_12','siemens_20','siemens_30','siemens_64','siemens_256','Custom...'])
    gradient_table = Str
    custom_gradient_table = File
    dsi_number_of_directions = Enum(514,[514,257,124])
    number_of_directions = Int(514)
    number_of_output_directions = Int(181)
    recon_matrix_file = Str('DSI_matrix_515x181.dat')
    apply_gradient_orientation_correction = Bool(True)
    number_of_averages = Int(1)
    multiple_high_b_values = Bool(False)
    number_of_b0_volumes = Int(1)
    
    compute_additional_maps = List(['gFA','skewness','kurtosis','P0'],
                                  editor=CheckListEditor(values=['gFA','skewness','kurtosis','P0'],cols=4))
    
    traits_view = View(Item('maximum_b_value',visible_when='imaging_model=="DTI"'),
                       Item('gradient_table_file',visible_when='imaging_model!="DSI"'),
                       Item('dsi_number_of_directions',visible_when='imaging_model=="DSI"'),
                       Item('number_of_directions',visible_when='imaging_model!="DSI"',enabled_when='gradient_table_file=="Custom..."'),
                       Item('custom_gradient_table',visible_when='imaging_model!="DSI"',enabled_when='gradient_table_file=="Custom..."'),
                       Item('number_of_averages',visible_when='imaging_model=="DTI"'),
                       Item('multiple_high_b_values',visible_when='imaging_model=="DTI"'),
                       'number_of_b0_volumes',
                       Item('apply_gradient_orientation_correction',visible_when='imaging_model!="DSI"'),
                       Item('compute_additional_maps',style='custom',visible_when='imaging_model!="DTI"'),
                       )
    
    def _dsi_number_of_directions_changed(self, new):
        self.number_of_directions = int(new)
        self.recon_matrix_file = 'DSI_matrix_%(n_directions)dx181.dat' % {'n_directions':int(new)+1}
        
    def _gradient_table_file_changed(self, new):
        if new != 'Custom...':
            self.gradient_table = os.path.join(pkg_resources.resource_filename('cmtklib',os.path.join('data','diffusion','gradient_tables')),new+'.txt')
            self.number_of_directions = int(re.search('\d+',new).group(0))
            
    def _custom_gradient_table_changed(self, new):
        self.gradient_table = new
        
    def _imaging_model_changed(self, new):
        if new == 'DTI' or new == 'HARDI':
            self._gradient_table_file_changed(self.gradient_table_file)
        if new == 'DSI':
            self._dsi_number_of_directions_changed(self.number_of_directions)

class MRtrix_recon_config(HasTraits):
    imaging_model = Str
    gradient_table_file = Enum('siemens_06',['mgh_dti_006','mgh_dti_018','mgh_dti_030','mgh_dti_042','mgh_dti_060','mgh_dti_072','mgh_dti_090','mgh_dti_120','mgh_dti_144',
                          'siemens_06','siemens_12','siemens_20','siemens_30','siemens_64','siemens_256','Custom...'])
    gradient_table = Str
    custom_gradient_table = File
    compute_CSD_editor = Dict({False:'1:Tensor',True:'2:Constrained Spherical Deconvolution'})
    compute_CSD = Bool(False)
    lmax_order = Enum(['Auto',2,4,6,8,10,12,14,16])
    normalize_to_B0 = Bool(False)
    single_fib_thr = Float(0.7,min=0,max=1)
    recon_mode = Str    
    
    traits_view = View(Item('gradient_table_file',label='Gradient table (x,y,z,b):'),
                       Item('custom_gradient_table',enabled_when='gradient_table_file=="Custom..."'),
                       Item('compute_CSD',editor=EnumEditor(name='compute_CSD_editor')),
		       Group(Item('lmax_order',editor=EnumEditor(values={'Auto':'1:Auto','2':'2:2','4':'3:4','6':'4:6','8':'5:8','10':'6:10','12':'7:12','14':'8:14','16':'9:16'})),
		       Item('normalize_to_B0'),
		       Item('single_fib_thr',label = 'FA threshold'),visible_when='compute_CSD'),
                       )
        
    def _gradient_table_file_changed(self, new):
        if new != 'Custom...':
            self.gradient_table = os.path.join(pkg_resources.resource_filename('cmtklib',os.path.join('data','diffusion','gradient_tables')),new+'.txt')
            self.number_of_directions = int(re.search('\d+',new).group(0))
            
    def _custom_gradient_table_changed(self, new):
        self.gradient_table = new
        
    def _imaging_model_changed(self, new):
        if new == 'DTI' or new == 'HARDI':
            self._gradient_table_file_changed(self.gradient_table_file)

    def _recon_mode_changed(self,new):
	if new == 'Probabilistic':
		self.compute_CSD_editor = {True:'Constrained Spherical Deconvolution'}
		self.compute_CSD = True
	else:
		self.compute_CSD_editor = {False:'1:Tensor',True:'2:Constrained Spherical Deconvolution'}

class Camino_recon_config(HasTraits):
    imaging_model = Str
    #build_scheme_file = Bool(False)
    #b_value = Int(1000)
    number_of_tensors = Enum('1',['1','2','3','Multitensor'])
    max_components = Int(1)
    diffusion_model = Str('dt')
    diffusion_model_editor = Dict({'dt':'Diffusion tensor','nldt_pos':'Non linear positive','nldt':'unconstrained non linear','ldt_wtd':'Diffusion weighted'})
    #recon_mode = Str
    
    gradient_table_file = Enum('siemens_06',['mgh_dti_006','mgh_dti_018','mgh_dti_030','mgh_dti_042','mgh_dti_060','mgh_dti_072','mgh_dti_090','mgh_dti_120','mgh_dti_144',
                          'siemens_06','siemens_12','siemens_20','siemens_30','siemens_64','siemens_256','Custom...'])
    gradient_table = Str
    custom_gradient_table = File
    
    traits_view = View(Item('diffusion_model',editor=EnumEditor(name='diffusion_model_editor')),
		       Item('gradient_table_file',label='Gradient table (x,y,z,b):'),
                       Item('custom_gradient_table',enabled_when='gradient_table_file=="Custom..."'),
		       VGroup('number_of_tensors',Item('max_components',enabled_when="number_of_tensors !=\'1\'")),
                       )

    def _number_of_tensors_changed(self,new):
	if new == '1':
		self.diffusion_model_editor = {'dt':'Linear fit','nldt_pos':'Non linear positive definite','nldt':'Unconstrained non linear','ldt_wtd':'Weighted linear fit'}
		self.diffusion_model = 'dt'
		self.max_components = 1
	elif new == '2':
		self.diffusion_model_editor = {'cylcyl':'bla1','cylcyl_eq':'bla2','pospos':'bla3','pospos_eq':'bla4','poscyl':'bla5','poscyl_eq':'bla6'}
		self.diffusion_model = 'cylcyl'
	elif new == '3':
		self.diffusion_model_editor = {'cylcylcyl':'bla7','cylcylcyl_eq':'bla8','pospospos':'bla9','pospospos_eq':'bla10','posposcyl':'bla11','posposcyl_eq':'bla12','poscylcyl':'bla13','poscylcyl_eq':'bla14'}
		self.diffusion_model = 'cylcylcyl'
	elif new == 'Multitensor':
		self.diffusion_model_editor = {'adc':'ADC','ball_stick':'Ball stick'}
		self.diffusion_model = 'adc'
        
    def _gradient_table_file_changed(self, new):
        if new != 'Custom...':
            self.gradient_table = os.path.join(pkg_resources.resource_filename('cmtklib',os.path.join('data','diffusion','gradient_tables')),new+'.txt')
            self.number_of_directions = int(re.search('\d+',new).group(0))
            
    def _custom_gradient_table_changed(self, new):
        self.gradient_table = new
        
    def _imaging_model_changed(self, new):
        if new == 'DTI' or new == 'HARDI':
            self._gradient_table_file_changed(self.gradient_table_file)
            
# Nipype interfaces for DTB commands

class DTB_P0InputSpec(CommandLineInputSpec):
    dsi_basepath = traits.Str(desc='DSI path/basename (e.g. \"data/dsi_\")',position=1,mandatory=True,argstr = "--dsi %s")
    dwi_file = nibase.File(desc='DWI file',position=2,mandatory=True,exists=True,argstr = "--dwi %s")

class DTB_P0OutputSpec(TraitedSpec):
    out_file = nibase.File(desc='Resulting P0 file')

class DTB_P0(CommandLine):
    _cmd = 'DTB_P0'
    input_spec = DTB_P0InputSpec
    output_spec = DTB_P0OutputSpec

    def _list_outputs(self):
        outputs = self._outputs().get()
        path, base, _ = split_filename(self.inputs.dsi_basepath)
        outputs["out_file"]  = os.path.join(path,base+'P0.nii')
        return outputs

class DTB_gfaInputSpec(CommandLineInputSpec):
    dsi_basepath = traits.Str(desc='DSI path/basename (e.g. \"data/dsi_\")',position=1,mandatory=True,argstr = "--dsi %s")
    moment = traits.Enum((2, 3, 4),desc='Moment to calculate (2 = gfa, 3 = skewness, 4 = curtosis)',position=2,mandatory=True,argstr = "--m %s")

class DTB_gfaOutputSpec(TraitedSpec):
    out_file = nibase.File(desc='Resulting file')

class DTB_gfa(CommandLine):
    _cmd = 'DTB_gfa'
    input_spec = DTB_gfaInputSpec
    output_spec = DTB_gfaOutputSpec

    def _list_outputs(self):
        outputs = self._outputs().get()
        path, base, _ = split_filename(self.inputs.dsi_basepath)

        if self.inputs.moment == 2:
            outputs["out_file"]  = os.path.join(path,base+'gfa.nii')
        if self.inputs.moment == 3:
            outputs["out_file"]  = os.path.join(path,base+'skewness.nii')
        if self.inputs.moment == 4:
            outputs["out_file"]  = os.path.join(path,base+'kurtosis.nii')

        return outputs
            
def strip_suffix(file_input, prefix):
    import os
    from nipype.utils.filemanip import split_filename
    path, _, _ = split_filename(file_input)
    return os.path.join(path, prefix+'_')
                        
def create_dtk_recon_flow(config):
    flow = pe.Workflow(name="reconstruction")
    
    # inputnode
    inputnode = pe.Node(interface=util.IdentityInterface(fields=["diffusion","diffusion_resampled"]),name="inputnode")
    
    outputnode = pe.Node(interface=util.IdentityInterface(fields=["DWI","B0","ODF","gFA","skewness","kurtosis","P0","max","V1"]),name="outputnode")
    
    if config.imaging_model == "DSI":
        prefix = "dsi"
        dtk_odfrecon = pe.Node(interface=dtk.ODFRecon(out_prefix=prefix),name='dtk_odfrecon')
        dtk_odfrecon.inputs.matrix = os.path.join(os.environ['DSI_PATH'],config.recon_matrix_file)
        dtk_odfrecon.inputs.n_b0 = config.number_of_b0_volumes
        dtk_odfrecon.inputs.n_directions = int(config.dsi_number_of_directions)+1
        dtk_odfrecon.inputs.n_output_directions = config.number_of_output_directions
        dtk_odfrecon.inputs.dsi = True
        
        flow.connect([
                    (inputnode,dtk_odfrecon,[('diffusion_resampled','DWI')]),
                    (dtk_odfrecon,outputnode,[('DWI','DWI'),('B0','B0'),('ODF','ODF'),('max','max')])])
                    
    if config.imaging_model == "HARDI":
        prefix = "hardi"
        dtk_hardimat = pe.Node(interface=dtk.HARDIMat(),name='dtk_hardimat')
        dtk_hardimat.inputs.gradient_table = config.gradient_table
        dtk_hardimat.inputs.oblique_correction = config.apply_gradient_orientation_correction
        
        dtk_odfrecon = pe.Node(interface=dtk.ODFRecon(out_prefix=prefix),name='dtk_odfrecon')
        dtk_odfrecon.inputs.n_b0 = config.number_of_b0_volumes
        dtk_odfrecon.inputs.n_directions = int(config.number_of_directions)+1
        dtk_odfrecon.inputs.n_output_directions = config.number_of_output_directions

        flow.connect([
                    (inputnode,dtk_hardimat,[('diffusion_resampled','reference_file')]),
                    (dtk_hardimat,dtk_odfrecon,[('out_file','matrix')]),
                    (inputnode,dtk_odfrecon,[('diffusion_resampled','DWI')]),
                    (dtk_odfrecon,outputnode,[('DWI','DWI'),('B0','B0'),('ODF','ODF'),('max','max')])])
                    
                        
    if config.imaging_model == "DTI":
        prefix = "dti"
        dtk_dtirecon = pe.Node(interface=dtk.DTIRecon(out_prefix=prefix),name='dtk_dtirecon')
        dtk_dtirecon.inputs.b_value = config.maximum_b_value
        dtk_dtirecon.inputs.gradient_matrix = config.gradient_table
        dtk_dtirecon.inputs.multiple_b_values = config.multiple_high_b_values
        dtk_dtirecon.inputs.n_averages = config.number_of_averages
        dtk_dtirecon.inputs.number_of_b0 = config.number_of_b0_volumes
        dtk_dtirecon.inputs.oblique_correction = config.apply_gradient_orientation_correction
        
        flow.connect([
                    (inputnode,dtk_dtirecon,[('diffusion','DWI')]),
                    (dtk_dtirecon,outputnode,[('DWI','DWI'),('B0','B0'),('V1','V1')])])
    else:
        if 'gFA' in config.compute_additional_maps:
            dtb_gfa = pe.Node(interface=DTB_gfa(moment=2),name='dtb_gfa')
            flow.connect([
                        (dtk_odfrecon,dtb_gfa,[(('ODF',strip_suffix,prefix),'dsi_basepath')]),
                        (dtb_gfa,outputnode,[('out_file','gFA')])])
        if 'skewness' in config.compute_additional_maps:
            dtb_skewness = pe.Node(interface=DTB_gfa(moment=3),name='dtb_skewness')
            flow.connect([
                        (dtk_odfrecon,dtb_skewness,[(('ODF',strip_suffix,prefix),'dsi_basepath')]),
                        (dtb_skewness,outputnode,[('out_file','skewness')])])
        if 'kurtosis' in config.compute_additional_maps:
            dtb_kurtosis = pe.Node(interface=DTB_gfa(moment=4),name='dtb_kurtosis')
            flow.connect([
                        (dtk_odfrecon,dtb_kurtosis,[(('ODF',strip_suffix,prefix),'dsi_basepath')]),
                        (dtb_kurtosis,outputnode,[('out_file','kurtosis')])])
        if 'P0' in config.compute_additional_maps:
            dtb_p0 = pe.Node(interface=DTB_P0(),name='dtb_P0')
            flow.connect([
                        (inputnode,dtb_p0,[('diffusion','dwi_file')]),
                        (dtk_odfrecon,dtb_p0,[(('ODF',strip_suffix,prefix),'dsi_basepath')]),
                        (dtb_p0,outputnode,[('out_file','P0')])])
                    
    return flow

class MRtrix_mul_InputSpec(CommandLineInputSpec):
    input1 = nibase.File(desc='Input1 file',position=1,mandatory=True,exists=True,argstr = "%s")
    input2 = nibase.File(desc='Input2 file',position=2,mandatory=True,exists=True,argstr = "%s")
    out_filename = traits.Str(desc='out filename',position=3,mandatory=True,argstr = "%s")

class MRtrix_mul_OutputSpec(TraitedSpec):
    out_file = nibase.File(desc='Multiplication result file')

class MRtrix_mul(CommandLine):
    _cmd = 'mrmult'
    input_spec = MRtrix_mul_InputSpec
    output_spec = MRtrix_mul_OutputSpec

    def _list_outputs(self):
        outputs = self._outputs().get()
        path, base, _ = split_filename(self.inputs.input1)
        outputs["out_file"]  = os.path.join(path,base+'_masked.mif')
        return outputs

def create_mrtrix_recon_flow(config):
    flow = pe.Workflow(name="reconstruction")
    inputnode = pe.Node(interface=util.IdentityInterface(fields=["diffusion","diffusion_resampled","wm_mask_resampled"]),name="inputnode")
    outputnode = pe.Node(interface=util.IdentityInterface(fields=["DWI","FA","eigVec","RF","SD","grad"],mandatory_inputs=True),name="outputnode")
    if config.compute_CSD:
	outputnode.inputs.SD = True
    else:
	outputnode.inputs.SD = False
    #outputnode.inputs.grad = config.gradient_table

    # Tensor
    mrtrix_tensor = pe.Node(interface=mrtrix.DWI2Tensor(),name='mrtrix_make_tensor')
    mrtrix_tensor.inputs.encoding_file = config.gradient_table
    #mrtrix_tensor.inputs.out_filename = 'dt.mif'
    flow.connect([
		(inputnode, mrtrix_tensor,[('diffusion_resampled','in_file')])
		])
    #mrtrix_mul.inputs.in_files = [

    # Tensor -> FA map
    mrtrix_FA = pe.Node(interface=mrtrix.Tensor2FractionalAnisotropy(),name='mrtrix_FA')
    #mrtrix_FA.inputs.out_filename = 'FA.mif'
    flow.connect([
		(mrtrix_tensor,mrtrix_FA,[('tensor','in_file')]),
		(mrtrix_FA,outputnode,[('FA','FA')])
		])

    # Tensor -> Eigenvectors
    mrtrix_eigVectors = pe.Node(interface=mrtrix.Tensor2Vector(),name="mrtrix_eigenvectors")
    #mrtrix_eigVectors.inputs.out_filename = 'ev.mif'
    flow.connect([
		(mrtrix_tensor,mrtrix_eigVectors,[('tensor','in_file')]),
		(mrtrix_eigVectors,outputnode,[('vector','eigVec')])
		])

    # Constrained Spherical Deconvolution
    if config.compute_CSD:
	# Compute single fiber voxel mask
	mrtrix_erode = pe.Node(interface=mrtrix.Erode(),name="mrtrix_erode")
	mrtrix_erode.inputs.number_of_passes = 3
	#mrtrix_mul_eroded_FA = pe.Node(interface=mrtrix.MRMultiply(),name='mrtrix_mul_eroded_FA')
	mrtrix_mul_eroded_FA = pe.Node(interface=MRtrix_mul(),name='mrtrix_mul_eroded_FA')
	mrtrix_mul_eroded_FA.inputs.out_filename = "/home/cmt/Documents/test_dataset/sub06/QBI64_b3000/NIPYPE/diffusion_pipeline/diffusion_stage/reconstruction/mrtrix_FA/diffusion_resampled_tensor_FA_masked.mif"
	mrtrix_thr_FA = pe.Node(interface=mrtrix.Threshold(),name='mrtrix_thr')
	mrtrix_thr_FA.inputs.absolute_threshold_value = config.single_fib_thr
	#mrtrix_thr_FA.inputs.out_filename = 'sf.mif'
	flow.connect([
		    (inputnode,mrtrix_erode,[("wm_mask_resampled",'in_file')]),
		    (mrtrix_erode,mrtrix_mul_eroded_FA,[('out_file','input2')]),
		    (mrtrix_FA,mrtrix_mul_eroded_FA,[('FA','input1')]),
		    (mrtrix_mul_eroded_FA,mrtrix_thr_FA,[('out_file','in_file')])
		    ])
	# Compute single fiber response function
	mrtrix_rf = pe.Node(interface=mrtrix.EstimateResponseForSH(),name="mrtrix_rf")
	mrtrix_rf.inputs.encoding_file = config.gradient_table
	if config.lmax_order != 'Auto':
		mrtrix_rf.inputs.maximum_harmonic_order = config.lmax_order
	#mrtrix_rf.inputs.out_filename = 'rf.mif'
	mrtrix_rf.inputs.normalise = config.normalize_to_B0
	flow.connect([
		    (inputnode,mrtrix_rf,[("diffusion_resampled","in_file")]),
		    (mrtrix_thr_FA,mrtrix_rf,[("out_file","mask_image")])
		    ])
	# Perform spherical deconvolution
	mrtrix_CSD = pe.Node(interface=mrtrix.ConstrainedSphericalDeconvolution(),name="mrtrix_CSD")
	mrtrix_CSD.inputs.normalise = config.normalize_to_B0
	mrtrix_CSD.inputs.encoding_file = config.gradient_table
	flow.connect([
		    (inputnode,mrtrix_CSD,[('diffusion_resampled','in_file')]),
		    (mrtrix_rf,mrtrix_CSD,[('response','response_file')]),
		    (mrtrix_rf,outputnode,[('response','RF')]),
		    (inputnode,mrtrix_CSD,[("wm_mask_resampled",'mask_image')]),
		    (mrtrix_CSD,outputnode,[('spherical_harmonics_image','DWI')])
		    ])
    else:
	flow.connect([
		    (inputnode,outputnode,[('diffusion_resampled','DWI')])
		    ])
    return flow

def create_camino_recon_flow(config):
    flow = pe.Workflow(name="reconstruction")
    inputnode = pe.Node(interface=util.IdentityInterface(fields=["diffusion","diffusion_resampled","wm_mask_resampled"]),name="inputnode")
    outputnode = pe.Node(interface=util.IdentityInterface(fields=["DWI","FA","MD","eigVec","RF","SD","grad"],mandatory_inputs=True),name="outputnode")
    
    # Convert diffusion data to camino format
    camino_convert = pe.Node(interface=camino.Image2Voxel(),name='camino_convert')
    flow.connect([
		(inputnode,camino_convert,[('diffusion_resampled','in_file')])
		])

    # Fit model
    camino_ModelFit = pe.Node(interface=camino.ModelFit(),name='camino_ModelFit')
    camino_ModelFit.inputs.model = config.diffusion_model
    camino_ModelFit.inputs.scheme_file = config.gradient_table

    flow.connect([
		(camino_convert,camino_ModelFit,[('voxel_order','in_file')]),
		(inputnode,camino_ModelFit,[('wm_mask_resampled','bgmask')]),
		(camino_ModelFit,outputnode,[('fitted_data','DWI')])
		])

    # Compute FA map
    camino_FA = pe.Node(interface=camino.ComputeFractionalAnisotropy(),name='camino_FA')
    if config.number_of_tensors == '1':
	camino_FA.inputs.inputmodel = 'dt'
    elif config.number_of_tensors == '2':
	camino_FA.inputs.inputmodel = 'twotensor'
    elif config.number_of_tensors == '3':
	camino_FA.inputs.inputmodel = 'threetensor'
    elif config.number_of_tensors == 'Multitensor':
	camino_FA.inputs.inputmodel = 'multitensor'

    flow.connect([
		(camino_ModelFit,camino_FA,[('fitted_data','in_file')]),
		(camino_FA,outputnode,[('fa','FA')]),
		])

    # Compute MD map
    camino_MD = pe.Node(interface=camino.ComputeMeanDiffusivity(),name='camino_MD')
    if config.number_of_tensors == '1':
	camino_MD.inputs.inputmodel = 'dt'
    elif config.number_of_tensors == '2':
	camino_MD.inputs.inputmodel = 'twotensor'
    elif config.number_of_tensors == '3':
	camino_MD.inputs.inputmodel = 'threetensor'
    elif config.number_of_tensors == 'Multitensor':
	camino_MD.inputs.inputmodel = 'multitensor'

    flow.connect([
		(camino_ModelFit,camino_MD,[('fitted_data','in_file')]),
		(camino_MD,outputnode,[('md','MD')]),
		])

    # Compute Eigenvalues
    camino_eigenvectors = pe.Node(interface=camino.ComputeEigensystem(),name='camino_eigenvectors')
    if config.number_of_tensors == '1':
	camino_eigenvectors.inputs.inputmodel = 'dt'
    else:
	camino_eigenvectors.inputs.inputmodel = 'multitensor'
    camino_eigenvectors.inputs.maxcomponents = config.max_components 

    flow.connect([
		(camino_ModelFit,camino_eigenvectors,[('fitted_data','in_file')]),
		(camino_eigenvectors,outputnode,[('eigen','eigVec')])
		])
    return flow
