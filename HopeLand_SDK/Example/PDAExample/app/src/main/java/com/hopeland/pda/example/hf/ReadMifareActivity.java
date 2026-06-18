package com.hopeland.pda.example.hf;

import com.hopeland.pda.example.R;
import com.pda.rfid.EPCModel;
import com.pda.rfid.IAsynchronousMessage;
import com.pda.rfid.hf.HF;
import com.pda.rfid.hf.HFReader;
import com.util.BaseActivity;

import android.content.DialogInterface;
import android.content.res.Configuration;
import android.os.Bundle;
import android.os.Message;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.AdapterView;
import android.widget.AdapterView.OnItemSelectedListener;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;

public class ReadMifareActivity extends BaseActivity implements
		IAsynchronousMessage {

	boolean busy = false;
	private int msgType = MSG_UPDATE_UID;

	/*
	 * 请求模式
	 */
	private Spinner sp_mifare_Model = null;

	/*
	 * UID
	 */
	private EditText tb_mifare_Uid = null;

	/*
	 * 位置、类型（用户区or钱包）
	 */
	private Spinner sp_mifare_Type = null;

	/*
	 * 块号
	 */
	private Spinner sp_mifare_Block = null;

	/*
	 * 传输块号
	 */
	private Spinner sp_mifare_TransBlock = null;

	/*
	 * 数据
	 */
	private EditText tb_mifare_Data = null;

	/*
	 * 块值操作（减、加、恢复）
	 */
	private Spinner sp_mifare_Mode = null;

	/*
	 * 认证方式
	 */
	private Spinner sp_mifare_CompareType = null;

	/*
	 * 密钥类别
	 */
	private Spinner sp_mifare_KeyType = null;

	/*
	 * 密钥
	 */
	private EditText tb_mifare_key = null;

	HF hfReader = HFReader.getHFInstance();

	static final int MSG_UPDATE_UID = MSG_USER_BEG + 1;

	@Override
	protected void msgProcess(Message msg) {
		switch (msg.what) {
		case MSG_UPDATE_UID:
			ShowUID(msg.obj.toString()); // 刷新列表
			break;
		default:
			super.msgProcess(msg);
			break;
		}
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		this.setContentView(R.layout.hf_mifare);
		ChangeLayout(getResources().getConfiguration());

		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.btn_HFMenu_Mifare),
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


	private void ChangeLayout(Configuration newConfig) {
		LinearLayout main = (LinearLayout)findViewById(R.id.view_split_main);
		LinearLayout left = (LinearLayout)findViewById(R.id.view_split_left);
		LinearLayout right = (LinearLayout)findViewById(R.id.view_split_right);

		if (newConfig.orientation == Configuration.ORIENTATION_LANDSCAPE) { //当前屏幕为横屏
			main.setOrientation(LinearLayout.HORIZONTAL);

			LinearLayout.LayoutParams leftParam = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, (float) 0.5);
			LinearLayout.LayoutParams rightParam = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, (float) 0.5);

			leftParam.setMargins(0, 0, 10, 0);
			rightParam.setMargins(10, 0, 0, 0);

			left.setLayoutParams(leftParam);
			right.setLayoutParams(rightParam);

		} else { // 当前屏幕为竖屏
			main.setOrientation(LinearLayout.VERTICAL);

			LinearLayout.LayoutParams leftParam = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
			LinearLayout.LayoutParams rightParam = (new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

			leftParam.setMargins(0, 0, 0, 0);
			rightParam.setMargins(0, 0, 0, 0);

			left.setLayoutParams(leftParam);
			right.setLayoutParams(rightParam);
		}

	}

	@Override
	public void onConfigurationChanged(Configuration newConfig) {
		super.onConfigurationChanged(newConfig);
		ChangeLayout(newConfig);
	}

	// 扫描标签
	public void ReadmifareUID(View v) {
		//
		tb_mifare_Uid.setText("");
		msgType = MSG_UPDATE_UID;
		String setParam = "IDEL";
		if (sp_mifare_Model != null) {
			setParam = sp_mifare_Model.getSelectedItem().toString();
		}
		if (setParam.equals("ALL")) {
			setParam = "52";
		} else {
			setParam = "26";
		}
		hfReader.GetISO14443ASN("0", setParam);
	}

	/*
	 * 读卡UID
	 */
	public void ShowUID(String uid) {
		tb_mifare_Uid.setText(uid);
	}

	/*
	 * 读
	 */
	public void mifareRead(View v) {
		tb_mifare_Data.setText("");
		String type = sp_mifare_Type.getSelectedItemPosition() + "";
		String block = sp_mifare_Block.getSelectedItem().toString();
		String dataLen = "16";
		if (type.equals("1")) {
			dataLen = "4";
		}
		String keyComfi = sp_mifare_CompareType.getSelectedItemId() + "";// "1"直接认证
		String keyType = "";
		String key = "";
		if (!keyComfi.equals("0")) {
			keyType = sp_mifare_KeyType.getSelectedItemId() + ""; // "0";//密钥A
			key = tb_mifare_key.getText().toString().replaceAll(" ", "");// "FFFFFFFFFFFF";//密钥
		}
		//
		String data = hfReader.ReadMifare(type, block, dataLen, keyComfi,
				keyType, key);
		//
		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			String[] contentStrings = data.split("\\|");
			showMsg(contentStrings[0] + "|" + getString(R.string.hf_read_faild),  null);
		} else {
			tb_mifare_Data.setText(data.substring(8, data.length()));
		}
	}

	/*
	 * 写
	 */
	public void mifareWrite(View v) {
		String data1 = tb_mifare_Data.getText().toString().replaceAll(" ", "");
		if (data1.equals("")) {
			super.showTip(getString(R.string.hf_mifare_value_empty));
			return;
		}
		String type = sp_mifare_Type.getSelectedItemPosition() + "";
		String block = sp_mifare_Block.getSelectedItem().toString();
		String keyComfi = sp_mifare_CompareType.getSelectedItemId() + "";// "1" 直接认证
		String keyType = "";
		String key = "";
		if (!keyComfi.equals("0")) {
			keyType = sp_mifare_KeyType.getSelectedItemId() + ""; // "0";//密钥A
			key = tb_mifare_key.getText().toString().replaceAll(" ", "");// "FFFFFFFFFFFF";//密钥
		}
		String data = hfReader.WriteMifare(type, block, keyComfi, data1,
				keyType, key);
		//
		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			showMsg(data, null);
		}
	}

	/*
	 * 块值
	 */
	public void mifareBlockValue(View v) {
		String data1 = tb_mifare_Data.getText().toString().replaceAll(" ", "");
		if (data1 == "") {
			super.showTip(getString(R.string.hf_mifare_value_empty));
			return;
		}
		String mode = "C0";
		int m = sp_mifare_Mode.getSelectedItemPosition();
		if (m == 1) {
			mode = "C1";
		} else if (m == 2) {
			mode = "C2";
		}
		String block = sp_mifare_Block.getSelectedItem().toString();
		String transBlock = sp_mifare_TransBlock.getSelectedItemPosition() + "";
		String keyComfi = sp_mifare_CompareType.getSelectedItemId() + "";// "1" 直接认证
		String keyType = "";
		String key = "";
		if (!keyComfi.equals("0")) {
			keyType = sp_mifare_KeyType.getSelectedItemId() + ""; // "0"密钥A
			key = tb_mifare_key.getText().toString().replaceAll(" ", "");// "FFFFFFFFFFFF"密钥
		}
		String data = hfReader.BlockCommandMifare(mode, block, data1,
				transBlock, keyComfi, keyType, key);
		//
		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			showMsg(data, null);
		}
	}

	// 退出
	public void Back(View v) {
		ReadMifareActivity.this.finish();
	}

	protected void Init() {
		if (!hfReader.OpenConnect(this)) { // 打开模块电源失败
			showMsg(getString(R.string.hf_low_power_info),
					new DialogInterface.OnClickListener() {
						@Override
						public void onClick(DialogInterface arg0, int arg1) {
							ReadMifareActivity.this.finish();
						}
					});
		} else {
			sp_mifare_Model = (Spinner) this.findViewById(R.id.sp_mifare_Model);
			tb_mifare_Uid = (EditText) this.findViewById(R.id.tb_mifare_Uid);
			sp_mifare_Type = (Spinner) this.findViewById(R.id.sp_mifare_Type);
			sp_mifare_Block = (Spinner) this.findViewById(R.id.sp_mifare_Block);
			sp_mifare_TransBlock = (Spinner) this
					.findViewById(R.id.sp_mifare_TransBlock);
			tb_mifare_Data = (EditText) this.findViewById(R.id.tb_mifare_Data);
			sp_mifare_Mode = (Spinner) this.findViewById(R.id.sp_mifare_Mode);
			sp_mifare_CompareType = (Spinner) this
					.findViewById(R.id.sp_mifare_CompareType);
			sp_mifare_KeyType = (Spinner) this
					.findViewById(R.id.sp_mifare_KeyType);
			tb_mifare_key = (EditText) this.findViewById(R.id.tb_mifare_key);
			tb_mifare_key.setText("FFFFFFFFFFFF");
			
			//
			sp_mifare_CompareType.setOnItemSelectedListener(new OnItemSelectedListenerImp());
			sp_mifare_KeyType.setOnItemSelectedListener(new OnItemSelectedListenerImp());
			
		}
	}
	
   class OnItemSelectedListenerImp implements OnItemSelectedListener{

		public void onItemSelected(AdapterView<?> parent, View view, int position,long id) {
			
		
		}

		public void onNothingSelected(AdapterView<?> arg0) {
		// TODO Auto-generated method stub
		}
	}


	protected void Dispose() {
		hfReader.CloseConnect();
	}

	@Override
	protected void onDestroy() {
		// 释放
		super.onDestroy();
		Dispose();
	}

	@Override
	protected void onPause() {
		// 待机锁屏
		super.onPause();
		Dispose();
	}

	@Override
	protected void onResume() {
		// 待机恢复
		super.onResume();
		Init();
	}

	@Override
	public void OutPutEPC(EPCModel model) {
		try {
			sendMessage(msgType, model._EPC);
		} catch (Exception ex) {
			Log.d("Debug", "Read the tag serial number exception:" + ex.getMessage());
		}
	}

}
