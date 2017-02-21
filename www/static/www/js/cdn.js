$(function(){
    $("button.add_domain").click(function(){
        $("p.input_domain").show();
    });
    $("button.add_sure").click(function(){
        if( $("input.domain_name").val() )
        {
            var tenantName = $("#tenantName").val();
            var app_id = $("#app_id").val();
            $.ajax({
                type : "POST",
                url : "/ajax/"+tenantName+"/"+app_id+"/domain/add",
                data : {
                    doamin : $("input.domain_name").val()
                },
                cache: false,
                success : function(data){
                    if(data["status"] == "success")
                    {
                        var str = "<tr><td>"+$("input.domain_name").val()+"</td>";
                        str += "<td>未审核</td>";
                        str += "<td>2017-02-19</td>";
                        str += "<td><a class='del_domain'>删除</a></td></tr>";
                        $(str).appendTo("tbody.domain_box");
                        $("p.input_domain").hide();
                        $("input.domain_name").val("");
                        del_domain();
                    }
                },
                error : function(){
                    swal("系统异常");
                }
            });
        }
        else{
            swal("请输入域名");
        }
    });
    $("button.add_cancel").click(function(){
        $("p.input_domain").hide();
        $("input.domain_name").val("");
    });
    del_domain();
    function del_domain(){
        $("a.del_domain").off('click');
        $("a.del_domain").on('click',function(){
            $.ajax({
                type : "POST",
                url : "",
                data : 123,
                cache: false,
                success : function(data){
                    $(this).parents("tr").remove();
                },
                error : function(){
                    swal("系统异常");
                }
            });
        });
    }

    $("button.add_operator").click(function(){
        $("p.input_operator").show();
    });
    $("button.operator_sure").click(function(){
        if( $("input.operator_name").val() && $("input.operator_realName").val() && $("input.operator_password").val() )
        {
            $.ajax({
                type : "POST",
                url : "",
                data : 123,
                cache: false,
                success : function(data){
                    var str = "<tr><td>"+$("input.operator_name").val()+"</td>";
                    str += "<td>"+$("input.operator_realName").val()+"</td>";
                    str += "<td class='operator_auth clearfix'>"+'<span class="check"></span><span class="text_auth">读取</span><span class="check"></span><span class="text_auth">写入</span><span class="check"></span><span class="text_auth">删除</span>'+"</td>";
                    str += '<td style="color:#28cb75;">正常</td>';
                    str += '<td>2017-02-17 12:00</td>';
                    str += "<td><a class='authorize_cancel'>取消权限</a></td></tr>";
                    $(str).appendTo("tbody.operator_box");
                    $("p.input_operator").hide();
                    $("input.operator_name").val("");
                    $("input.operator_realName").val("");
                    $("input.operator_password").val("");
                    del_operator();
                },
                error : function(){
                    swal("系统异常");
                }
            });
        }
        else{
            swal("请输入信息");
        }
    });
    $("button.operator_cancel").click(function(){
        $("p.input_operator").hide();
        $("input.operator_name").val("");
        $("input.operator_realName").val("");
        $("input.operator_password").val("");
    });
    del_operator();
    function del_operator(){
        $("a.del_operator").off('click');
        $("a.del_operator").on('click',function(){
            $.ajax({
                type : "POST",
                url : "",
                data : 123,
                cache: false,
                success : function(data){
                    $(this).parents("tr").remove();
                },
                error : function(){
                    swal("系统异常");
                }
            });
        });
    }


    editPort();
    function editPort(){
        $('.edit-port').editable({
            type: 'text',
            pk: 1,
            success: function (data) {
                
            },
            error: function (data) {
                msg = data.responseText;
                res = $.parseJSON(msg);
                showMessage(res.info);
            },
            ajaxOptions: {
                beforeSend: function(xhr, settings) {
                    xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
                    settings.data += '&action=change_port';
                },
            }
            //validate: function (value) {
            //    if (!$.trim(value)) {
            //        return '不能为空';
            //    }
            //    else if($(this).hasClass("enviromentKey"))
            //    {
            //        var variableReg = /^[A-Z][A-Z0-9_]*$/;
            //        if( !variableReg.test($(".editable-input").find("input").val()) )
            //        {
            //            return '变量名由大写字母与数字组成且大写字母开头';
            //        }
            //    }
            //}
        });
    }
})