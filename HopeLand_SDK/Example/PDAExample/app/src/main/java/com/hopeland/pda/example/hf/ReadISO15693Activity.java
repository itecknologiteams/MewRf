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
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;

public class ReadISO15693Activity extends BaseActivity implements
		IAsynchronousMessage {

	boolean busy = false;
	private int msgType = MSG_UPDATE_UID;

	private EditText tb_iso15693_AFI = null;
	private EditText tb_iso15693_DSFID = null;
	private EditText tb_iso15693_WriteData = null;
	private EditText tb_Access_Uid = null;
	private Spinner sp_Write_Block = null;

	HF hfReader = HFReader.getHFInstance();

	static final int MSG_UPDATE_UID = MSG_USER_BEG + 1;
	static final int MSG_UPDATE_READ_DATA = MSG_USER_BEG + 2;
	static final int MSG_UPDATE_CARD_INFO = MSG_USER_BEG + 3;

	@Override
	protected void msgProcess(Message msg) {

		switch (msg.what) {
		case MSG_UPDATE_UID:
			ShowUID(msg.obj.toString()); // 刷新列表
			break;
		case MSG_UPDATE_READ_DATA:
			ShowReadData(msg.obj.toString()); // 刷新列表
			break;
		case MSG_UPDATE_CARD_INFO:
			ShowCardInfo(msg.obj.toString()); // 刷新列表
			break;
		default:
			super.msgProcess(msg);
			break;
		}
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		this.setContentView(R.layout.hf_iso15693);
		ChangeLayout(getResources().getConfiguration());

		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.btn_HFMenu_ISO15693),
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

	// 扫描标签，读卡序列号
	public void ReadUID(View v) {
		msgType = MSG_UPDATE_UID;
		tb_Access_Uid.setText("");
		hfReader.GetISO15693SN("00", "00");
	}

	/*
	 * 读卡UID
	 */
	public void ShowUID(String uid) {
		tb_Access_Uid.setText(uid);
	}

	// 读块
	public void Read(View v) {
		tb_iso15693_WriteData.setText("");
		msgType = MSG_UPDATE_READ_DATA;
		String setParam = "00";
		if (sp_Write_Block != null) {
			setParam = sp_Write_Block.getSelectedItem().toString();
		}
		String data = hfReader.ReadISO15693("00", setParam, "00");

		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			showMsg(data, null);
		} else {
			tb_iso15693_WriteData.setText(data.substring(10, data.length()));
		}
	}

	/*
	 * 读卡块数据
	 */
	public void ShowReadData(String blockData) {

		tb_iso15693_WriteData.setText(blockData);
	}

	// 写块
	public void Write(View v) {
		String setParam1 = "00";
		if (sp_Write_Block != null) {
			setParam1 = sp_Write_Block.getSelectedItem().toString();
		}
		String setParam2 = ""; //"11223344";
		String data1 = tb_iso15693_WriteData.getText().toString().replaceAll(" ", "");
		if (data1.equals("")) {
			super.showTip(getString(R.string.hf_mifare_value_empty));
			return;
		}
		setParam2 = data1;
		String data = hfReader.WriteISO15693("00", setParam1, "00", setParam2);
		//
		if (data.equals("")) {
			return;
		}
		
	    showMsg(data, null);
		
	}

	// 获取卡信息
	public void GetInfo(View v) {
		tb_iso15693_WriteData.setText("");
		msgType = MSG_UPDATE_CARD_INFO;
		String data = hfReader.ReadISO15693("01", "", "");
		//
		if (data.equals("")) {
			return;
		}
		if (data.contains("|")) {
			showMsg(data, null);
		} else {
			tb_iso15693_WriteData.setText(data.substring(8, data.length()));
		}
	}

	/*
	 * 读卡详细信息
	 */
	public void ShowCardInfo(String cardInfo) {

		tb_iso15693_WriteData.setText(cardInfo);
	}

	// 写AFI
	public void writeAFI(View v) {
		@SuppressWarnings("unused")
		String setParam1 = "00";
		if (tb_iso15693_AFI != null) {
			setParam1 = tb_iso15693_AFI.getText().toString();
		}
		String data = hfReader.WriteISO15693("01", "", "", "01");
		showMsg(data, null);
	}

	// 锁AFI
	public void lockAFI(View v) {
		String data = hfReader.LockISO15693("01", "");
		showMsg(data, null);
	}

	// 写DSFID
	public void writeDSFID(View v) {
		@SuppressWarnings("unused")
		String setParam1 = "00";
		if (tb_iso15693_DSFID != null) {
			setParam1 = tb_iso15693_DSFID.getText().toString();
		}
		String data = hfReader.WriteISO15693("02", "", "", "01");
		showMsg(data, null);
	}

	// 锁DSFID
	public void lockDSFID(View v) {
		String data = hfReader.LockISO15693("02", "");
		showMsg(data, null);
	}

	// 退出
	public void Back(View v) {
		ReadISO15693Activity.this.finish();
	}

	protected void Init() {
		if (!hfReader.OpenConnect(this)) { // 打开模块电源失败
			showMsg(getString(R.string.hf_low_power_info),
					new DialogInterface.OnClickListener() {
						@Override
						public void onClick(DialogInterface arg0, int arg1) {
							ReadISO15693Activity.this.finish();
						}
					});
		} else {
			sp_Write_Block = (Spinner) this.findViewById(R.id.sp_Write_Block);
			tb_Access_Uid = (EditText) this.findViewById(R.id.tb_Access_Uid);
			tb_iso15693_WriteData = (EditText) this
					.findViewById(R.id.tb_iso15693_WriteData);
			tb_iso15693_DSFID = (EditText) this
					.findViewById(R.id.tb_iso15693_DSFID);
			tb_iso15693_AFI = (EditText) this
					.findViewById(R.id.tb_iso15693_AFI);
		}
	}

	protected void Dispose() {
		hfReader.CloseConnect();
	}

	@Override
	protected void onDestroy() {
		// 释放
		super.onDestroy();
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
