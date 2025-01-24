
create_project -force fw fw -part xczu9eg-ffvb1156-2-e

variable design_name
set design_name fw

create_bd_design $design_name
current_bd_design $design_name

##################################################################
# DESIGN PROCs
##################################################################


# Procedure to create entire design
proc create_root_design { parentCell } {

  # Create interface ports
  set AXIS_RX [ create_bd_intf_port -mode Slave -vlnv xilinx.com:interface:axis_rtl:1.0 AXIS_RX ]
  set_property -dict [ list \
   CONFIG.HAS_TKEEP {0} \
   CONFIG.HAS_TLAST {1} \
   CONFIG.HAS_TREADY {1} \
   CONFIG.HAS_TSTRB {0} \
   CONFIG.LAYERED_METADATA {undef} \
   CONFIG.TDATA_NUM_BYTES {4} \
   CONFIG.TDEST_WIDTH {0} \
   CONFIG.TID_WIDTH {0} \
   CONFIG.TUSER_WIDTH {0} \
   ] $AXIS_RX

  set AXIS_TX [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:axis_rtl:1.0 AXIS_TX ]

  set S_AXI [ create_bd_intf_port -mode Slave -vlnv xilinx.com:interface:aximm_rtl:1.0 S_AXI ]
  set_property -dict [ list \
   CONFIG.ADDR_WIDTH {15} \
   CONFIG.ARUSER_WIDTH {0} \
   CONFIG.AWUSER_WIDTH {0} \
   CONFIG.BUSER_WIDTH {0} \
   CONFIG.DATA_WIDTH {32} \
   CONFIG.HAS_BRESP {1} \
   CONFIG.HAS_BURST {1} \
   CONFIG.HAS_CACHE {1} \
   CONFIG.HAS_LOCK {1} \
   CONFIG.HAS_PROT {1} \
   CONFIG.HAS_QOS {0} \
   CONFIG.HAS_REGION {0} \
   CONFIG.HAS_RRESP {1} \
   CONFIG.HAS_WSTRB {1} \
   CONFIG.ID_WIDTH {0} \
   CONFIG.MAX_BURST_LENGTH {1} \
   CONFIG.NUM_READ_OUTSTANDING {2} \
   CONFIG.NUM_READ_THREADS {1} \
   CONFIG.NUM_WRITE_OUTSTANDING {2} \
   CONFIG.NUM_WRITE_THREADS {1} \
   CONFIG.PROTOCOL {AXI4LITE} \
   CONFIG.READ_WRITE_MODE {READ_WRITE} \
   CONFIG.RUSER_BITS_PER_BYTE {0} \
   CONFIG.RUSER_WIDTH {0} \
   CONFIG.SUPPORTS_NARROW_BURST {0} \
   CONFIG.WUSER_BITS_PER_BYTE {0} \
   CONFIG.WUSER_WIDTH {0} \
   ] $S_AXI


  # Create ports
  set aclk [ create_bd_port -dir I -type clk aclk ]
  set_property -dict [ list \
   CONFIG.ASSOCIATED_RESET {areset} \
 ] $aclk
  set areset [ create_bd_port -dir I -type rst areset ]
  set_property -dict [ list \
   CONFIG.POLARITY {ACTIVE_HIGH} \
 ] $areset

  # Create instance: smartconnect_0, and set properties
  set smartconnect_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0 ]
  set_property -dict [list \
    CONFIG.NUM_MI {2} \
    CONFIG.NUM_SI {1} \
  ] $smartconnect_0


  # Create instance: axi_bram_ctrl_0, and set properties
  set axi_bram_ctrl_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_bram_ctrl:4.1 axi_bram_ctrl_0 ]
  set_property CONFIG.PROTOCOL {AXI4LITE} $axi_bram_ctrl_0


  # Create instance: axi_fifo_mm_s_0, and set properties
  set axi_fifo_mm_s_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_fifo_mm_s:4.3 axi_fifo_mm_s_0 ]
  set_property -dict [list \
    CONFIG.C_USE_RX_DATA {1} \
    CONFIG.C_USE_TX_CTRL {0} \
    CONFIG.C_USE_TX_DATA {1} \
  ] $axi_fifo_mm_s_0


  # Create instance: blk_mem_gen_0, and set properties
  set blk_mem_gen_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen:8.4 blk_mem_gen_0 ]
  set_property CONFIG.Memory_Type {True_Dual_Port_RAM} $blk_mem_gen_0


  # Create instance: util_vector_logic_0, and set properties
  set util_vector_logic_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 util_vector_logic_0 ]
  set_property -dict [list \
    CONFIG.C_OPERATION {not} \
    CONFIG.C_SIZE {1} \
  ] $util_vector_logic_0


  # Create interface connections
  connect_bd_intf_net -intf_net AXI_STR_RXD_0_1 [get_bd_intf_ports AXIS_RX] [get_bd_intf_pins axi_fifo_mm_s_0/AXI_STR_RXD]
  connect_bd_intf_net -intf_net S_AXI_1 [get_bd_intf_ports S_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
  connect_bd_intf_net -intf_net axi_bram_ctrl_0_BRAM_PORTA [get_bd_intf_pins axi_bram_ctrl_0/BRAM_PORTA] [get_bd_intf_pins blk_mem_gen_0/BRAM_PORTA]
  connect_bd_intf_net -intf_net axi_bram_ctrl_0_BRAM_PORTB [get_bd_intf_pins axi_bram_ctrl_0/BRAM_PORTB] [get_bd_intf_pins blk_mem_gen_0/BRAM_PORTB]
  connect_bd_intf_net -intf_net axi_fifo_mm_s_0_AXI_STR_TXD [get_bd_intf_ports AXIS_TX] [get_bd_intf_pins axi_fifo_mm_s_0/AXI_STR_TXD]
  connect_bd_intf_net -intf_net smartconnect_0_M00_AXI [get_bd_intf_pins axi_bram_ctrl_0/S_AXI] [get_bd_intf_pins smartconnect_0/M00_AXI]
  connect_bd_intf_net -intf_net smartconnect_0_M01_AXI [get_bd_intf_pins axi_fifo_mm_s_0/S_AXI] [get_bd_intf_pins smartconnect_0/M01_AXI]

  # Create port connections
  connect_bd_net -net aresetn_1 [get_bd_ports areset] [get_bd_pins util_vector_logic_0/Op1]
  connect_bd_net -net s_axi_aclk_0_1 [get_bd_ports aclk] [get_bd_pins axi_bram_ctrl_0/s_axi_aclk] [get_bd_pins axi_fifo_mm_s_0/s_axi_aclk] [get_bd_pins smartconnect_0/aclk]
  connect_bd_net -net util_vector_logic_0_Res [get_bd_pins axi_bram_ctrl_0/s_axi_aresetn] [get_bd_pins axi_fifo_mm_s_0/s_axi_aresetn] [get_bd_pins smartconnect_0/aresetn] [get_bd_pins util_vector_logic_0/Res]

  # Create address segments
  assign_bd_address -offset 0x00000000 -range 0x00001000 -target_address_space [get_bd_addr_spaces S_AXI] [get_bd_addr_segs axi_bram_ctrl_0/S_AXI/Mem0] -force
  assign_bd_address -offset 0x00001000 -range 0x00001000 -target_address_space [get_bd_addr_spaces S_AXI] [get_bd_addr_segs axi_fifo_mm_s_0/S_AXI/Mem0] -force


  validate_bd_design
  save_bd_design
}
# End of create_root_design()


##################################################################
# MAIN FLOW
##################################################################

create_root_design ""

set wrapper_file [make_wrapper -files [get_files -filter {FILE_TYPE == "Block Designs"}] -top -import]
set_property top fw_wrapper [current_fileset -simset]

# update_compile_order -fileset [current_fileset]
# set_property -name {xsim.elaborate.xelab.more_options} -value {-dll} -objects [current_fileset -simset]

launch_simulation -absolute_path  -scripts_only

close_project
exit
