package com.hopeland.pda.example.uhf;

import java.util.regex.*;

import android.content.res.Configuration;
import com.hopeland.pda.example.PublicData;
import com.hopeland.pda.example.R;
import com.pda.rfid.uhf.UHFReader;
import com.port.Adapt;
import com.pda.rfid.EPCModel;
import com.pda.rfid.IAsynchronousMessage;
import com.util.Helper.Helper_String;

import android.content.DialogInterface;
import android.os.Bundle;
import android.os.Message;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.*;

/**
 * @author RFID_C Write Tag
 */
public class WriteEPCActivity extends UHFBaseActivity implements
		IAsynchronousMessage {

	private static int _WriteType = 0;

	private EditText tb_Write_MatchTID = null;
	private EditText tb_Access_Password = null;
	private Spinner sp_Write_WriteType = null;
	private EditText tb_Write_WriteData = null;

	private final int MSG_MATCH_READ = MSG_USER_BEG + 1; // constant

	@Override
	protected void msgProcess(Message msg) {
		switch (msg.what) {
		case MSG_MATCH_READ:
			ShowMatchTID(msg.obj.toString()); // Refresh the list
			break;
		default:
			super.msgProcess(msg);
			break;
		}
	}

	public void ShowMatchTID(String tid) {
		tb_Write_MatchTID.setText(tid);
	}

	//init
	protected void Init() {
		// do not using backup power in write
		if (!UHF_Init(this)) { // Failed to open the power supply
			showMsg(getString(R.string.uhf_low_power_info),
					new DialogInterface.OnClickListener() {
						@Override
						public void onClick(DialogInterface arg0, int arg1) {
							WriteEPCActivity.this.finish();
						}
					});
		} else {
			// Initialize object
			tb_Write_MatchTID = (EditText) findViewById(R.id.tb_Write_MatchTID);
			tb_Access_Password = (EditText) findViewById(R.id.tb_Access_Password);
			tb_Access_Password.setText("00000000");
			tb_Write_WriteData = (EditText) findViewById(R.id.tb_Write_WriteData);
			sp_Write_WriteType = (Spinner) findViewById(R.id.sp_Write_WriteType);

			// The data type to write
			sp_Write_WriteType
					.setOnItemSelectedListener(new Spinner.OnItemSelectedListener() {

						@Override
						public void onItemSelected(AdapterView<?> arg0,
								View arg1, int arg2, long arg3) {

							int selectItem = sp_Write_WriteType
									.getSelectedItemPosition();
							if (selectItem == 0) {
								_WriteType = 0;
							} else if (selectItem == 1) {
								_WriteType = 1;
							}
							else if(selectItem == 2){
								_WriteType = 2;
							}
						}

						@Override
						public void onNothingSelected(AdapterView<?> arg0) {
							// TODO Auto-generated method stub

						}

					});

		}
	}

	//Dispose
	protected void Dispose() {
		UHF_Dispose();
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		// TODO 创建
		super.onCreate(savedInstanceState);
		this.setContentView(R.layout.uhf_wirte);
		ChangeLayout(getResources().getConfiguration());

		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.btn_UHFMenu_Write),
				getString(R.string.str_back), null,
				R.drawable.left, 0,
				new View.OnClickListener() {
					@Override
					public void onClick(View v) {
						Back(v);
					}
				},
				null
		);
	}

	@Override
	public void onConfigurationChanged(Configuration newConfig) {
		super.onConfigurationChanged(newConfig);
		ChangeLayout(newConfig);
	}

	@Override
	protected void onDestroy() {
		// destroy
		super.onDestroy();
	}

	@Override
	protected void onPause() {
		super.onPause();
		Dispose();
	}

	@Override
	protected void onResume() {
		super.onResume();
		Init();
		super.UHF_GetReaderProperty();
	}

	boolean in_reading = false;
	// Read the tag TID that you want to write
	public void ReadMactchTag(View v) {

		sendMessage(MSG_MATCH_READ,"");
		in_reading = true;
		String rt="";
		int ret=-1;
		if (PublicData._IsCommand6Cor6B.equals("6C")) {// 6C
            ret = UHFReader._Tag6C.GetEPC_TID(_NowAntennaNo, 1);
		} else { // 6B
			rt = CLReader.Get6B(_NowAntennaNo + "|1" + "|0");
		}

		//After reading the tag for 2 seconds, stop
		new Thread() {
			public void run() {
				int wait = 50;
				int timout = 2000;
				showWait(getString(R.string.waiting));
				try {
					for (int i=0; i<timout; i+=wait) {
						Thread.sleep(wait);
						if (!in_reading) {
							break;
						}
					}
					UHFReader._Config.Stop(); //You must stop reading or the write tag will fail
				} catch (Exception e) {
				}
				hideWait();
			};
		}.start();
	}

	// Write
	public void WirteData(View v) {
		int dataLen = 0; // 写入数据长度
		String strInput = tb_Write_WriteData.getText().toString();
		if (!CheckInput(strInput)) { // check
			showMsg(getString(R.string.uhf_data_error), null);
			return;
		}
		if(_WriteType == 2) //AccessPassword
		{
			if(tb_Write_WriteData.getText().length()!=8){
				showMsg(getString(R.string.uhf_data_len_error), null);
				return;
			}
		}
		dataLen = tb_Write_WriteData.getText().length() % 4 == 0 ? tb_Write_WriteData
				.getText().length() / 4
				: tb_Write_WriteData.getText().length() / 4 + 1;
		if (dataLen > 0) {
			if (PublicData._IsCommand6Cor6B.equals("6C")) {// 6C
			    int ret=-1;
				if (_WriteType == 0) { // EPC
                    //UHFReader._Tag6C.WriteEPC(_NowAntennaNo,tb_Write_WriteData.getText().toString());
                    ret=UHFReader._Tag6C.WriteEPC_MatchTID(_NowAntennaNo,tb_Write_WriteData.getText().toString(),tb_Write_MatchTID.getText().toString(),0);
				} else if (_WriteType == 1) { // UserData
                    //UHFReader._Tag6C.WriteUserData(_NowAntennaNo,tb_Write_WriteData.getText().toString());
                    ret=UHFReader._Tag6C.WriteUserData_MatchTID(_NowAntennaNo,tb_Write_WriteData.getText().toString(),tb_Write_MatchTID.getText().toString(),0);
				}
				else if(_WriteType == 2){//AccessPassword
                    //UHFReader._Tag6C.WriteAccessPassWord(_NowAntennaNo,tb_Write_WriteData.getText().toString());
                    ret=UHFReader._Tag6C.WriteAccessPassWord_MatchTID(_NowAntennaNo,tb_Write_WriteData.getText().toString(),tb_Write_MatchTID.getText().toString(),
                            0,tb_Access_Password.getText().toString());
                }
                if (ret == 0) {
                    showMsg(getString(R.string.str_success), null);
                } else {
                    showMsg(getString(R.string.str_faild), null);
                }
			} else {
				Write6B(tb_Write_WriteData.getText().toString());
			}
		} else {
			showMsg(getString(R.string.uhf_data_error), null);
		}

	}

	// write 6B
	public void Write6B(String sEPC) {
		String param = "";
		int AntNum = _NowAntennaNo;
		param += AntNum + "|";
		param += tb_Write_MatchTID.getText().toString() + "|";
		param += "8" + "|";
		param += sEPC;
		if (CLReader.Write6B(param).startsWith("0")) {
			showMsg(getString(R.string.str_success), null);
		} else {
			showMsg(getString(R.string.str_faild), null);
		}
	}

	//check the input
	public boolean CheckInput(String strInput) {
		boolean rt = false;
		Pattern p = Pattern.compile("^[a-f,A-F,0-9]*$");
		Matcher m = p.matcher(strInput);
		rt = m.matches();
		return rt;
	}

	// back
	public void Back(View v) {
		Dispose();

		WriteEPCActivity.this.finish();
	}

	@Override
	public void OutPutEPC(EPCModel model) {
		if (in_reading) {
			sendMessage(MSG_MATCH_READ, model._TID);
			in_reading = false;
		}
	}
}
